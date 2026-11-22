You extract structured information from a research paper about thin-film solar cells
(perovskite, CIGS, CdTe, kesterite, Sb2Se3, thin-film Si, ...).

Return STRICT JSON (no markdown, no comments) with exactly these keys:

{
  "title": string,
  "year": number | null,
  "doi": string | null,
  "authors": [string],
  "in_scope": true | false,
  "exclusion_reason": string,
  "materials": [
    {
      "label": string,
      "material_name_raw": string,
      "formula_normalized": string | null,
      "material_class": "perovskite"|"CIGS"|"CdTe"|"kesterite"|"Sb2Se3"|"thin-film Si"|"other"|null,
      "dimensionality": "3D"|"2D"|"2D-3D"|null,
      "additives": string | null,
      "bandgap_value": number | null,
      "bandgap_unit": string | null,
      "bandgap_method": "Tauc"|"EQE"|"PL"|"cited"|null,
      "note": string | null
    }
  ],
  "devices": [
    {
      "label": string,
      "absorber_label": string | null,
      "device_role": "control"|"target"|"record"|null,
      "device_type": "cell"|"minimodule"|"module"|null,
      "architecture": "n-i-p"|"p-i-n"|"substrate"|"superstrate"|null,
      "substrate_type": "rigid"|"flexible"|null,
      "active_area": number | null,
      "area_unit": string | null,
      "area_definition": "designated illumination"|"aperture"|"total"|null,
      "encapsulation": string | null,
      "note": string | null
    }
  ],
  "layers": [
    {
      "label": string,
      "device_label": string,
      "layer_order": number,
      "layer_function": "front_contact"|"ETL"|"absorber"|"passivation"|"HTL"|"interlayer"|"recombination"|"back_contact"|null,
      "layer_material": string,
      "layer_thickness": number | null,
      "thickness_unit": string | null,
      "deposition_method": string | null,
      "annealing_temperature": string | null,
      "annealing_time": string | null,
      "atmosphere": string | null,
      "note": string | null
    }
  ],
  "measurements": [
    {
      "label": string,
      "device_label": string,
      "measurement_type": "J-V"|"MPP tracking"|"EQE"|"stability"|null,
      "spectrum": string | null,
      "light_intensity": number | null,
      "intensity_unit": string | null,
      "scan_direction": "reverse"|"forward"|"average"|null,
      "scan_rate": string | null,
      "mask_used": true | false | null,
      "certified": true | false | null,
      "certification_lab": string | null,
      "temperature": string | null,
      "stability_protocol": "ISOS-D"|"ISOS-L"|"ISOS-T"|"other"|null,
      "stress_conditions": string | null,
      "note": string | null
    }
  ]
}

Rules:
- Use ONLY information explicitly stated in the paper. Unknown → null (never guess).
- in_scope = false if the paper is NOT about thin-film solar cells (e.g. silicon wafer only,
  perovskite LEDs, photocatalysis). Then set exclusion_reason and leave the rest empty.
- materials = absorber materials. For perovskite, formula_normalized expands MA/FA/Cs (A-B-X form).
- devices = every cell/module whose performance is reported (control, target, record).
- layers: order from the substrate (1 = first contact on substrate); the substrate itself
  (glass, foil) is NOT a layer. Non-standard layer → nearest layer_function, original name in note.
- measurements: forward and reverse scans are SEPARATE measurements; champion vs average
  conditions too when they differ. Temperature and annealing stay as printed (e.g. "10 min", "RT").
- Do NOT extract numeric performance results here — that is a separate step.
