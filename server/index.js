import express from 'express';
import multer from 'multer';
import path from 'node:path';
import fs from 'node:fs';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const app = express();
const PORT = process.env.PORT || 3001;

// Папка для загруженных PDF (создаётся автоматически)
const uploadDir = path.resolve(__dirname, '..', 'uploads');
fs.mkdirSync(uploadDir, { recursive: true });

const MAX_FILE_SIZE = 50 * 1024 * 1024; // 50 МБ

// Безопасное имя файла: убираем всё, кроме букв/цифр/точек/дефисов
const sanitizeName = (name) => name.replace(/[^\w.\-а-яёА-ЯЁ]/gu, '_');

const storage = multer.diskStorage({
  destination: uploadDir,
  filename: (req, file, cb) => {
    cb(null, `${Date.now()}-${sanitizeName(file.originalname)}`);
  },
});

const upload = multer({
  storage,
  limits: { fileSize: MAX_FILE_SIZE },
  fileFilter: (req, file, cb) => {
    // multer/busboy декодирует имя файла как latin1 — возвращаем UTF-8 (кириллица и т.д.)
    file.originalname = Buffer.from(file.originalname, 'latin1').toString('utf8');
    const isPdf =
      file.mimetype === 'application/pdf' ||
      path.extname(file.originalname).toLowerCase() === '.pdf';
    if (!isPdf) {
      return cb(new Error('Разрешены только PDF-файлы'));
    }
    cb(null, true);
  },
});

app.use(express.json());

// Загрузка одного PDF: поле формы "file"
app.post('/api/upload', upload.single('file'), (req, res) => {
  if (!req.file) {
    return res.status(400).json({ error: 'Файл не получен' });
  }
  res.status(201).json({
    id: path.basename(req.file.filename, '.pdf'),
    filename: req.file.filename,
    originalName: req.file.originalname,
    size: req.file.size,
    uploadedAt: new Date().toISOString(),
  });
});

// Список загруженных файлов
app.get('/api/files', (req, res) => {
  const files = fs
    .readdirSync(uploadDir)
    .filter((f) => f.toLowerCase().endsWith('.pdf'))
    .map((f) => {
      const stat = fs.statSync(path.join(uploadDir, f));
      return { filename: f, size: stat.size, uploadedAt: stat.mtime.toISOString() };
    })
    .sort((a, b) => b.uploadedAt.localeCompare(a.uploadedAt));
  res.json(files);
});

// Отдача загруженного файла по имени
app.get('/api/files/:filename', (req, res) => {
  const safe = sanitizeName(path.basename(req.params.filename));
  const filePath = path.join(uploadDir, safe);
  if (!fs.existsSync(filePath)) {
    return res.status(404).json({ error: 'Файл не найден' });
  }
  res.sendFile(filePath);
});

// Ошибки multer (размер, тип файла и т.д.)
app.use((err, req, res, next) => {
  if (err instanceof multer.MulterError) {
    const msg = err.code === 'LIMIT_FILE_SIZE'
      ? 'Файл слишком большой (максимум 50 МБ)'
      : err.message;
    return res.status(400).json({ error: msg });
  }
  if (err) {
    return res.status(400).json({ error: err.message });
  }
  next();
});

app.listen(PORT, () => {
  console.log(`Upload server: http://localhost:${PORT}`);
});
