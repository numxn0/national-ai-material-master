# Canonical Material Schema Specification
**National AI Material Master for Indian CPSEs / PSUs**

*Version:* 1.0.0  
*Document Status:* Approved Specification & Architectural Plan  
*Target Platforms:* National AI Material Master Engine, Supabase PostgreSQL, Hybrid AI Deduplication Core  

---

## 1. Purpose of the Canonical Schema

### 1.1 The CPSE / PSU Material Master Fragmentation Problem
Across India's Central Public Sector Enterprises (CPSEs)—such as Indian Railways, Steel Authority of India Limited (SAIL), Oil and Natural Gas Corporation (ONGC), National Thermal Power Corporation (NTPC), Coal India Limited (CIL), Bharat Heavy Electricals Limited (BHEL), and Indian Oil Corporation Limited (IOCL)—industrial inventory cataloging has evolved independently over decades. 

Each enterprise operates separate Enterprise Resource Planning (ERP) installations (e.g., SAP ECC, SAP S/4HANA, Oracle e-Business Suite, IBM Maximo, or bespoke in-house systems). This siloed evolution has generated massive operational inefficiencies:

```
[ Indian Railways ERP ]  --> "BEARING 6205-2RS SKF DGBB"        (Item: IR-045821)
[ Coal India ERP ]       --> "BRG BALL 6205 2RS RUBBER SEAL"    (Item: CIL-M-9910)  ===> IDENTICAL PHYSICAL ITEM
[ NTPC Plant MMS ]       --> "DEEP GROOVE BRG 25X52X15 6205 2RS" (Item: NTPC-40112)
```

1. **Syntactic and Lexical Inconsistencies:** Identical items are cataloged with varying word orders, abbreviations (`SS` vs `STAINLESS STL` vs `AISI-304`), punctuation, and typos.
2. **Unit of Measure (UOM) Discrepancies:** The same item may be tracked as `NOS` in one PSU, `SET` or `EA` in another, and `KGS` or `MTR` in bulk storage.
3. **Hidden Overlapping Inventory:** PSUs hold hundreds of crores in surplus inventory while sister enterprises issue emergency tenders to procure the exact same spare parts from common OEMs at inflated rates.
4. **Lack of Attribute Structuring:** Critical specifications (bore size, schedule, pressure rating, voltage, metallurgy standard) remain trapped in unparsed, free-form text descriptions.

### 1.2 Strategic Objectives of the Canonical Schema
The **Canonical Material Schema** establishes an authoritative, normalized, and machine-interpretable data contract. Every CPSE material record ingested into the National AI Material Master is transformed into this standard representation before duplicate detection, clustering, machine learning matching, human review, and national code assignment.

The schema achieves five core objectives:
* **Deduplication:** Decouples legacy descriptions into discrete, normalized attribute-value pairs, enabling deterministic and semantic deduplication across millions of items.
* **Standardization:** Enforces standard engineering taxonomies (e.g., UNSPSC, NIC, BIS, ISO, ASTM, DIN) and ISO/BIS Units of Measure across all public sector organizations.
* **AI Matching:** Provides high-density feature inputs (normalized tokens, dense semantic embeddings, structured technical attributes) for hybrid AI matching pipelines (RapidFuzz + pgvector + XGBoost/SHAP).
* **Governance & Stewardship:** Supports a rigorous multi-tier validation workflow where enterprise nodal officers and national steering committees review and ratify links.
* **Auditability & Provenance:** Maintains an immutable audit trail connecting every national master item to its constituent legacy records, recording every confidence score, matching rule, and reviewer action.

---

## 2. Difference Between Source Material and National Material

The platform strictly separates operational inputs from ratified national standards via an **N:1 (Many-to-One)** relationship model:

```
+-------------------------------------------------------------+
|               SOURCE MATERIALS (N Records)                  |
|  - Mutable, raw/cleaned records from CPSE ERPs              |
|  - Retain local provenance, local codes, and local UOMs     |
+-------------------------------------------------------------+
       |                           |                     |
   [SAIL ERP]                 [ONGC SAP]            [IOCL Maximo]
   "SS304 PIPE 2 INCH"        "PIPE SS 50NB SCH40"   "ASTM A312 TP304 50 NB"
       \                           |                     /
        \                          |                    /
         +-------------------------+-------------------+
                                   |
                     [ AI Matching & Dual-Tier Review ]
                                   |
                                   v
+-------------------------------------------------------------+
|               NATIONAL MATERIAL (1 Golden Record)           |
|  - Immutable, ratified National SKU (NAMM Code)             |
|  - Standard description, canonical attributes, standard UOM |
|  - Authoritative classification path and governance history |
+-------------------------------------------------------------+
```

### 2.1 Source Material (`source_material`)
* **Definition:** A digital snapshot of an item as it exists in a specific CPSE or PSU enterprise management system.
* **Role:** Serves as the raw evidence and operational link. It captures historical purchase codes, regional plant descriptions, local units of measure, and legacy supplier identifiers.
* **Cardinality:** Multiple source material records can originate from different CPSEs—or even different regional plants within the same CPSE—that refer to the exact same physical manufactured product.

### 2.2 National Material (`national_material`)
* **Definition:** The single, unified, canonical "Golden Record" approved at the national inter-CPSE level to represent an unambiguous, unique industrial product or specification.
* **Role:** Acts as the single source of truth for all public procurement, vendor benchmarking, inter-CPSE inventory pooling, and national demand forecasting.
* **Key Characteristics:** 
  * Assigned an official, hierarchically structured **National Material Code** (e.g., `NAMM-PIP-SS-0042`).
  * Governed by formal ratification states (`ACTIVE`, `DEPRECATED`, `UNDER_REVIEW`).
  * Backed by canonical engineering attributes and standard international/national standards (BIS, ASTM, ISO).

### 2.3 Cardinality Relationship
A single `national_material` record maps to **one or more** `source_material` records. A `source_material` record maps to **at most one** ratified `national_material` record (or remains in an unlinked candidate state pending discovery or consensus).

---

## 3. Canonical Source Material Fields (22 Fields)

Every record ingested from an external CPSE catalog is normalized into the following standard source material structure:

| Field Name | Data Type | Nullable | Description & Business Rules |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | No | Globally unique identifier (v4 UUID) generated upon ingestion. |
| `source_cpse` | `VARCHAR(100)` | No | Name or acronym of the originating CPSE (e.g., `SAIL`, `ONGC`, `INDIAN_RAILWAYS`, `NTPC`, `CIL`, `BHEL`, `IOCL`). |
| `source_system` | `VARCHAR(100)` | No | Originating IT system/ERP instance (e.g., `SAP_ECC_PROD`, `ORACLE_EBS_WR`, `MAXIMO_PLANT_04`, `GEP_SMART`). |
| `source_material_code`| `VARCHAR(120)` | No | Local item code / material master number in the CPSE system (e.g., `NR-6205-2RS`, `IOCL-VLV-4INCH`). |
| `raw_description` | `TEXT` | No | Exact verbatim text from source database before any transformation, preserved for auditability. |
| `cleaned_description`| `TEXT` | No | Sanitized text: lowercased, Unicode normalized (NFKD), punctuation standardized, whitespace collapsed. |
| `standard_description`| `TEXT` | No | AI-structured title formatted according to national naming standard (`Noun, Modifier, Key Specs, Standard`). |
| `category` | `VARCHAR(120)` | No | Standardized high-level taxonomy group (e.g., `PIPING_AND_FITTINGS`, `ROTATING_MACHINERY`, `ELECTRICAL`). |
| `sub_category` | `VARCHAR(120)` | No | Standardized secondary taxonomy level (e.g., `PIPES`, `BEARINGS`, `VALVES`, `CABLES`, `MOTORS`). |
| `material_type` | `VARCHAR(120)` | Yes | Specific engineering subtype (e.g., `SEAMLESS_PIPE`, `DEEP_GROOVE_BALL_BEARING`, `BALL_VALVE`). |
| `material_grade` | `VARCHAR(100)` | Yes | Metallurgical, chemical, or performance grade standard (e.g., `SS304`, `ASTM A312 TP304`, `GRADE 8.8`, `IS 694`). |
| `manufacturer` | `VARCHAR(150)` | Yes | Normalized brand or OEM manufacturer name (e.g., `SKF`, `FAG`, `L&T`, `POLYCAB`, `SIEMENS`, `BHUSHAN_STEEL`). |
| `part_number` | `VARCHAR(120)` | Yes | Cleaned manufacturer catalog part number (e.g., `6205-2RS`, `1.1KV-3C-2.5`, `FIG-52`). |
| `model_number` | `VARCHAR(120)` | Yes | OEM commercial model or frame series designation (e.g., `1LA7080-4AA10`, `SERIES-300`). |
| `uom` | `VARCHAR(20)` | No | Standardized Unit of Measure (ISO 3-character uppercase format: `NOS`, `MTR`, `KGS`, `LTR`, `SET`). |
| `attributes` | `JSONB` | No | Structured key-value map of extracted technical specifications (e.g., dimensions, ratings, standards). |
| `normalized_tokens` | `TEXT[]` | No | Array of lemmatized, stopword-stripped, domain-specific tokens for fast lexical searching and indexing. |
| `ingestion_batch_id`| `UUID` | No | Foreign key reference linking the record to its data batch import job. |
| `match_status` | `VARCHAR(40)` | No | AI pipeline status: `UNPROCESSED`, `MATCH_FOUND`, `NEW_CANDIDATE`, `AMBIGUOUS_MATCH`, `NO_MATCH`. |
| `approval_status` | `VARCHAR(40)` | No | Workflow status: `PENDING_INGESTION`, `PENDING_L1_REVIEW`, `PENDING_L2_REVIEW`, `APPROVED`, `REJECTED`. |
| `created_at` | `TIMESTAMPTZ` | No | ISO 8601 timestamp with timezone recording the exact ingestion time. |
| `updated_at` | `TIMESTAMPTZ` | No | ISO 8601 timestamp with timezone recording the latest modification or state change. |

---

## 4. Canonical National Material Fields (15 Fields)

When one or more source materials are consolidated and approved, they correspond to a single National Material Master record:

| Field Name | Data Type | Nullable | Description & Business Rules |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | No | Globally unique identifier (v4 UUID) for the national master record. |
| `national_material_code`| `VARCHAR(60)` | No | Unique, official national code formatted hierarchically (e.g., `NAMM-PIP-SS-0042`, `NAMM-MEC-BRG-0192`). |
| `standard_description`| `TEXT` | No | Official golden description constructed according to National Cataloging Guidelines. |
| `category` | `VARCHAR(120)` | No | Canonical top-level category aligned with national classification standards. |
| `sub_category` | `VARCHAR(120)` | No | Canonical sub-category grouping. |
| `material_type` | `VARCHAR(120)` | No | Standard physical design or component classification. |
| `material_grade` | `VARCHAR(100)` | Yes | Recognized standard material grade (ASTM, BIS, DIN, ISO). |
| `standard_uom` | `VARCHAR(20)` | No | Authoritative national procurement Unit of Measure (e.g., `NOS`, `MTR`, `KGS`). |
| `canonical_attributes`| `JSONB` | No | Certified, canonical specification dictionary representing the authoritative physical properties. |
| `classification_path`| `VARCHAR(255)` | No | Dot-delimited or slash-delimited hierarchical taxonomy path (e.g., `MEC.ROTATING.BEARINGS.BALL.DEEP_GROOVE`). |
| `status` | `VARCHAR(40)` | No | Operational lifecycle state: `DRAFT`, `ACTIVE`, `UNDER_REVIEW`, `DEPRECATED`, `SUPERSEDED`. |
| `created_by` | `VARCHAR(100)` | No | Identity of the automated system agent or national cataloger creating the record. |
| `approved_by` | `VARCHAR(100)` | Yes | Identity/Sign-off of the national committee chair or Tier-2 authority ratifying the record. |
| `created_at` | `TIMESTAMPTZ` | No | Timestamp when the national master record was created. |
| `updated_at` | `TIMESTAMPTZ` | No | Timestamp of the latest specification update or lifecycle transition. |

---

## 5. Material Mapping Fields (10 Fields)

The bridge between legacy source materials and canonical national materials is established through explicit, explainable mapping entities:

| Field Name | Data Type | Nullable | Description & Business Rules |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | No | Globally unique primary key for the mapping linkage. |
| `source_material_id` | `UUID` | No | Foreign key reference to `source_materials(id)`. |
| `national_material_id`| `UUID` | No | Foreign key reference to `national_materials(id)`. |
| `confidence_score` | `NUMERIC(5,4)`| No | Overall composite match confidence score between `0.0000` and `1.0000` (e.g., `0.9425`). |
| `match_method` | `VARCHAR(50)` | No | Matching technique utilized: `EXACT_CODE`, `RULE_BASED`, `COSINE_VECTOR`, `XGBOOST_HYBRID`, `MANUAL`. |
| `match_explanation` | `JSONB` | No | Machine-readable breakdown detailing why the match was generated (SHAP values, feature deltas, token overlap). |
| `approval_status` | `VARCHAR(40)` | No | Governance status: `AUTO_MATCHED`, `PENDING_L1`, `PENDING_L2`, `APPROVED`, `REJECTED`, `DISPUTED`. |
| `reviewer_id` | `VARCHAR(100)` | Yes | User ID or identifier of the officer who reviewed and approved/rejected the linkage. |
| `reviewed_at` | `TIMESTAMPTZ` | Yes | Timestamp of the review decision. |
| `created_at` | `TIMESTAMPTZ` | No | Timestamp when the match was discovered or proposed. |

---

## 6. Attribute Examples (JSON)

Below are realistic technical attribute JSON structures for key industrial material categories.

### 6.1 Stainless Steel Pipe
```json
{
  "nominal_bore_nb": 50,
  "nominal_bore_unit": "mm",
  "nominal_bore_inch": 2.0,
  "outer_diameter_mm": 60.3,
  "schedule": "SCH 40",
  "wall_thickness_mm": 3.91,
  "material_grade": "ASTM A312 TP304",
  "metallurgy": "Stainless Steel 304",
  "manufacturing_process": "SEAMLESS",
  "ends": "PLAIN_END",
  "length_meters": 6.0,
  "governing_standard": "ASTM A312",
  "pressure_rating_psi": 1200,
  "uom": "MTR"
}
```

### 6.2 Bearing
```json
{
  "bearing_type": "DEEP_GROOVE_BALL_BEARING",
  "iso_designation": "6205-ZZ",
  "bore_diameter_mm": 25,
  "outer_diameter_mm": 52,
  "width_thickness_mm": 15,
  "shielding_sealing": "DOUBLE_METAL_SHIELD",
  "clearance": "C3",
  "cage_material": "STEEL",
  "dynamic_load_rating_kn": 14.8,
  "static_load_rating_kn": 7.8,
  "limiting_speed_rpm": 15000,
  "governing_standard": "ISO 15 / IS 6458",
  "manufacturer": "SKF",
  "part_number": "6205 ZZ C3",
  "uom": "NOS"
}
```

### 6.3 Valve
```json
{
  "valve_type": "BALL_VALVE",
  "nominal_diameter_dn": 50,
  "nominal_diameter_unit": "mm",
  "nominal_diameter_inch": 2.0,
  "pressure_rating_class": "PN16",
  "body_material": "A182 F304 / SS304",
  "ball_material": "SS304",
  "seat_material": "PTFE",
  "end_connection": "FLANGED",
  "flange_standard": "ASME B16.5 / DIN 2501",
  "bore_type": "FULL_BORE",
  "operation": "LEVER_OPERATED",
  "design_standard": "BS 5351 / API 6D",
  "fire_safe": true,
  "manufacturer": "L&T VALVES",
  "part_number": "BV-SS-50-PN16-F",
  "uom": "NOS"
}
```

### 6.4 Electrical Cable
```json
{
  "cable_type": "POWER_AND_CONTROL_CABLE",
  "voltage_grade_kv": "1.1KV",
  "number_of_cores": 3,
  "cross_section_sqmm": 2.5,
  "conductor_material": "ELECTROLYTIC_COPPER",
  "conductor_class": "CLASS_2_STRANDED",
  "insulation_type": "PVC",
  "inner_sheath": "EXTRUDED_PVC",
  "armouring_type": "GALVANIZED_STEEL_ROUND_WIRE",
  "outer_sheath": "PVC_TYPE_ST2_FLAME_RETARDANT",
  "operating_temp_max_c": 70,
  "governing_standard": "IS 1554 PART 1 / IS 694",
  "manufacturer": "POLYCAB",
  "part_number": "POL-1.1-3C2.5-CU-ARM",
  "uom": "MTR"
}
```

### 6.5 Electric Motor
```json
{
  "motor_type": "DC_MOTOR",
  "voltage": 24,
  "voltage_unit": "V DC",
  "power_hp": 0.5,
  "power_kw": 0.373,
  "rated_speed_rpm": 1500,
  "full_load_current_amps": 18.5,
  "torque_nm": 2.37,
  "frame_size": "IEC-71M",
  "enclosure_ip_rating": "IP55",
  "insulation_class": "CLASS_F",
  "duty_cycle": "S1_CONTINUOUS",
  "cooling_method": "IC411_TEFC",
  "mounting_type": "B3_FOOT_MOUNTED",
  "manufacturer": "CROMPTON_GREAVES",
  "model_number": "24V-0.5HP-1500-DC",
  "uom": "NOS"
}
```

---

## 7. Normalized Record Examples

Below are complete, fully populated canonical source material records as they appear in the system following sanitization, attribute extraction, and tokenization.

### 7.1 SS PIPE 50 NB SCH 40 ASTM A312
```json
{
  "id": "7a942b2e-9d21-4f4c-83b6-194ce0291ba1",
  "source_cpse": "IOCL",
  "source_system": "SAP_ECC_PRD",
  "source_material_code": "IOCL-P-304-50NB",
  "raw_description": "PIPE S.S. 50 NB SCH 40 ASTM A312 GR TP 304 SEAMLESS 6M",
  "cleaned_description": "pipe ss 50 nb sch 40 astm a312 gr tp 304 seamless 6m",
  "standard_description": "Pipe, Stainless Steel, Seamless, 50 NB (2 Inch), Schedule 40, ASTM A312 TP304, Plain Ends, L=6M",
  "category": "PIPING_AND_FITTINGS",
  "sub_category": "PIPES",
  "material_type": "SEAMLESS_PIPE",
  "material_grade": "ASTM A312 TP304",
  "manufacturer": "JINDAL_SAW",
  "part_number": "JND-304-50-SCH40",
  "model_number": null,
  "uom": "MTR",
  "attributes": {
    "nominal_bore_nb": 50,
    "nominal_bore_inch": 2.0,
    "outer_diameter_mm": 60.3,
    "schedule": "SCH 40",
    "wall_thickness_mm": 3.91,
    "material_grade": "ASTM A312 TP304",
    "manufacturing_process": "SEAMLESS",
    "length_meters": 6.0,
    "ends": "PLAIN_END",
    "standard": "ASTM A312",
    "uom": "MTR"
  },
  "normalized_tokens": [
    "pipe", "stainless", "steel", "seamless", "50", "nb", "schedule", "40", "astm", "a312", "tp304", "6m"
  ],
  "ingestion_batch_id": "c3e1b7f0-0d3a-4a25-9b2f-7c1a8d5e9f02",
  "match_status": "MATCH_FOUND",
  "approval_status": "APPROVED",
  "created_at": "2026-09-19T06:30:00.000Z",
  "updated_at": "2026-09-19T06:35:12.000Z"
}
```

### 7.2 BEARING 6205 ZZ
```json
{
  "id": "e2f183c4-4b52-47d9-bb20-918342a71e89",
  "source_cpse": "INDIAN_RAILWAYS",
  "source_system": "IREPS_NORTHERN_RAILWAY",
  "source_material_code": "NR-MECH-BRG-6205ZZ",
  "raw_description": "BALL BEARING 6205 ZZ SKF C3 METALLIC SHIELD BOTH SIDES",
  "cleaned_description": "ball bearing 6205 zz skf c3 metallic shield both sides",
  "standard_description": "Bearing, Ball, Deep Groove, 6205-ZZ, Bore 25mm, OD 52mm, Width 15mm, Double Metal Shielded, C3 Clearance",
  "category": "MECHANICAL_SPARES",
  "sub_category": "BEARINGS",
  "material_type": "DEEP_GROOVE_BALL_BEARING",
  "material_grade": "SAE 52100 / 100CR6",
  "manufacturer": "SKF",
  "part_number": "6205 ZZ C3",
  "model_number": "6205-ZZ",
  "uom": "NOS",
  "attributes": {
    "bearing_type": "DEEP_GROOVE_BALL_BEARING",
    "iso_number": "6205",
    "bore_diameter_mm": 25,
    "outer_diameter_mm": 52,
    "width_mm": 15,
    "shield_type": "ZZ_DOUBLE_METAL_SHIELD",
    "internal_clearance": "C3",
    "standard": "ISO 15 / IS 6458",
    "uom": "NOS"
  },
  "normalized_tokens": [
    "bearing", "ball", "deep", "groove", "6205", "zz", "25mm", "52mm", "15mm", "skf", "c3", "shield"
  ],
  "ingestion_batch_id": "c3e1b7f0-0d3a-4a25-9b2f-7c1a8d5e9f02",
  "match_status": "MATCH_FOUND",
  "approval_status": "APPROVED",
  "created_at": "2026-09-19T06:30:00.000Z",
  "updated_at": "2026-09-19T06:35:12.000Z"
}
```

### 7.3 24V DC MOTOR 0.5 HP
```json
{
  "id": "55b88231-15cf-4df7-873b-5a1e2f3d99c4",
  "source_cpse": "BHEL",
  "source_system": "SAP_ECC_HARIDWAR",
  "source_material_code": "BHEL-MOT-24VDC-05HP",
  "raw_description": "MOTOR DC 24 VOLT 0.5HP 1500RPM FOOT MOUNTED IP55 CROMPTON",
  "cleaned_description": "motor dc 24 volt 0.5hp 1500rpm foot mounted ip55 crompton",
  "standard_description": "Electric Motor, DC Shunt, 24V DC, 0.5 HP (0.373 kW), 1500 RPM, Frame IEC 71M, Foot Mounted B3, IP55, Class F",
  "category": "ELECTRICAL",
  "sub_category": "MOTORS",
  "material_type": "DC_MOTOR",
  "material_grade": "CLASS_F_INSULATION",
  "manufacturer": "CROMPTON_GREAVES",
  "part_number": "CG-DC24-05-B3",
  "model_number": "24V-0.5HP-1500",
  "uom": "NOS",
  "attributes": {
    "voltage": 24,
    "voltage_type": "DC",
    "power_hp": 0.5,
    "power_kw": 0.373,
    "rated_speed_rpm": 1500,
    "frame_size": "IEC-71M",
    "mounting": "B3_FOOT",
    "ingress_protection": "IP55",
    "insulation_class": "CLASS_F",
    "standard": "IS 4722 / IEC 60034",
    "uom": "NOS"
  },
  "normalized_tokens": [
    "motor", "dc", "24v", "24", "volt", "0.5", "hp", "1500", "rpm", "foot", "b3", "ip55", "crompton"
  ],
  "ingestion_batch_id": "c3e1b7f0-0d3a-4a25-9b2f-7c1a8d5e9f02",
  "match_status": "MATCH_FOUND",
  "approval_status": "APPROVED",
  "created_at": "2026-09-19T06:30:00.000Z",
  "updated_at": "2026-09-19T06:35:12.000Z"
}
```

### 7.4 PVC INSULATED COPPER CABLE 3 CORE 2.5 SQMM
```json
{
  "id": "119f8e24-cc09-417e-9762-59821ef37da8",
  "source_cpse": "NTPC",
  "source_system": "SAP_S4HANA_VINDHYACHAL",
  "source_material_code": "NTPC-ELC-CBL-3C25",
  "raw_description": "CABLE 1.1 KV COPPER CONDUCTOR PVC INSULATED ARMOURED 3CX2.5 SQMM IS 1554",
  "cleaned_description": "cable 1.1 kv copper conductor pvc insulated armoured 3cx2.5 sqmm is 1554",
  "standard_description": "Power Cable, 1.1 kV, 3 Core x 2.5 sqmm, Stranded Electrolytic Copper, PVC Insulated, Steel Wire Armoured, PVC Outer Sheathed, IS 1554 Part 1",
  "category": "ELECTRICAL",
  "sub_category": "CABLES",
  "material_type": "POWER_AND_CONTROL_CABLE",
  "material_grade": "IS 1554 PART 1",
  "manufacturer": "POLYCAB",
  "part_number": "POL-1.1-3C2.5-ARMD",
  "model_number": "CBL-3C-2.5",
  "uom": "MTR",
  "attributes": {
    "voltage_rating_kv": "1.1KV",
    "number_of_cores": 3,
    "cross_section_sqmm": 2.5,
    "conductor_material": "COPPER",
    "insulation": "PVC",
    "armouring": "ARMOURED_STEEL_WIRE",
    "governing_standard": "IS 1554 PART 1",
    "uom": "MTR"
  },
  "normalized_tokens": [
    "cable", "1.1kv", "copper", "cu", "pvc", "armoured", "armd", "3", "core", "3c", "2.5", "sqmm", "is1554"
  ],
  "ingestion_batch_id": "c3e1b7f0-0d3a-4a25-9b2f-7c1a8d5e9f02",
  "match_status": "MATCH_FOUND",
  "approval_status": "APPROVED",
  "created_at": "2026-09-19T06:30:00.000Z",
  "updated_at": "2026-09-19T06:35:12.000Z"
}
```

### 7.5 BALL VALVE 50MM SS304 PN16
```json
{
  "id": "908c4b12-28e1-4c12-b184-f7b539a2d813",
  "source_cpse": "ONGC",
  "source_system": "MAXIMO_HAZIRA_PLANT",
  "source_material_code": "ONGC-VLV-BALL-50",
  "raw_description": "BALL VALVE 50 MM NB SS 304 BODY FLANGED END PN 16 FULL BORE LEVER OP",
  "cleaned_description": "ball valve 50 mm nb ss 304 body flanged end pn 16 full bore lever op",
  "standard_description": "Ball Valve, 50mm NB (2 Inch), Rating PN16, SS304 Body, SS304 Ball, PTFE Seat, Flanged Ends, Full Bore, Lever Operated, BS 5351",
  "category": "PIPING_AND_FITTINGS",
  "sub_category": "VALVES",
  "material_type": "BALL_VALVE",
  "material_grade": "ASTM A182 F304 / SS304",
  "manufacturer": "L&T_VALVES",
  "part_number": "LTV-BV-50-PN16",
  "model_number": "SERIES-50-FLG",
  "uom": "NOS",
  "attributes": {
    "valve_type": "BALL_VALVE",
    "nominal_diameter_mm": 50,
    "nominal_diameter_inch": 2.0,
    "pressure_rating": "PN16",
    "body_material": "SS304",
    "trim_material": "SS304",
    "seat_material": "PTFE",
    "end_connection": "FLANGED",
    "bore_type": "FULL_BORE",
    "operation": "LEVER_OPERATED",
    "standard": "BS 5351 / ASME B16.5",
    "uom": "NOS"
  },
  "normalized_tokens": [
    "valve", "ball", "50mm", "50", "nb", "ss304", "stainless", "flanged", "pn16", "full", "bore", "lever"
  ],
  "ingestion_batch_id": "c3e1b7f0-0d3a-4a25-9b2f-7c1a8d5e9f02",
  "match_status": "MATCH_FOUND",
  "approval_status": "APPROVED",
  "created_at": "2026-09-19T06:30:00.000Z",
  "updated_at": "2026-09-19T06:35:12.000Z"
}
```

---

## 8. Matching Relevance

The canonical schema is explicitly engineered to feed the platform's multi-stage AI matching engine. Rather than relying on monolithic string comparison, the engine breaks comparison into orthogonal feature channels:

```
+-------------------------------------------------------------------------------+
|                       Multi-Stage AI Matching Pipeline                        |
+-------------------------------------------------------------------------------+
       |
       +---> [1. Categorical Block Filter]   : Category, Sub-category, Type
       |
       +---> [2. Lexical & Token Similarity] : Levenshtein, Token Sort/Set Ratio
       |
       +---> [3. Semantic Vector Cosine]    : Sentence-Transformers (all-MiniLM-L6)
       |
       +---> [4. Parametric Attribute Match] : JSON key-value compatibility
       |
       +---> [5. Engineering Rule Engine]   : Grade, Standard, Dimension crosswalk
       |
       v
  [ XGBoost Ensemble Classifier + SHAP Explainability Engine ]
       |
       +---> Confidence >= 0.90 ==> Auto-Link Candidate
       +---> 0.70 <= Conf < 0.90 ==> Flag for Human-in-the-Loop Review Queue
       +---> Confidence < 0.70  ===> Designate as New National SKU Candidate
```

### 8.1 Description Similarity
* **Tokens & Lemmatization:** `normalized_tokens` strips noise words ("for", "with", "genuine", "plant-2") and applies domain-specific synonym substitutions (`SS` -> `stainless steel`, `BRG` -> `bearing`, `CU` -> `copper`).
* **Fuzzy Matchers:** RapidFuzz calculates Token Sort Ratio, Token Set Ratio, and Partial Ratio, preventing penalties due to rearranged word orders (e.g., `BEARING SKF 6205` vs `SKF 6205 BEARING`).
* **Dense Semantic Embeddings:** Text fields are encoded into 384-dimensional dense vectors using models like `sentence-transformers/all-MiniLM-L6-v2`. Even if token overlap is low, semantic proximity captures domain relationships (e.g., `hex bolt` and `hexagon screw`).

### 8.2 Extracted Attributes
* **Parametric Intersection:** Technical parameters stored in `attributes` (e.g., `voltage`, `nominal_bore_nb`, `power_hp`) are compared programmatically.
* **Exact vs Range Checking:** Critical fields require exact equality (e.g., `number_of_cores = 3`), while continuous specs allow tolerance thresholds (e.g., ±0.5% on resistance or weight).
* **Attribute Compatibility Score:** Computes Jaccard similarity across shared keys and numerical Euclidean proximity across shared numeric metrics.

### 8.3 Category / Sub-Category
* **Search Space Pruning:** The classification hierarchy serves as an aggressive indexing blocker. A query for `PIPING_AND_FITTINGS / VALVES` immediately prunes candidates in `ELECTRICAL / MOTORS` from the candidate generation pool.
* **Hierarchical Tree Distance:** If an item is borderline between two sub-categories (e.g., `CABLES` vs `WIRES`), taxonomy tree distance quantifies categorical alignment.

### 8.4 UOM Compatibility
* **Unit Dimension Conversion:** Differences in UOM often cause false negatives in naive matching. The schema incorporates a Unit Conversion Matrix:
  * Dimension / Length: `MTR` <-> `MM` <-> `FT` <-> `INCH`
  * Packaging: `NOS` <-> `EA` <-> `PIECE` <-> `SET`
  * Weight / Mass: `KGS` <-> `MT` <-> `TON` <-> `LBS`
* **Mismatch Penalties:** A mismatch between incompatible dimensions (e.g., `MTR` [length] vs `KGS` [weight]) immediately flags a potential packaging or assembly discrepancy.

### 8.5 Manufacturer / Part Number
* **OEM Part Number Hashing:** Standardized part numbers (e.g., `6205-ZZ`, `3C2.5-PVC-CU`) undergo alphanumeric stripping (hyphens, spaces, slashes removed). An exact stripped part number match yields high base confidence.
* **Manufacturer Alias Resolution:** A normalized manufacturer dictionary maps aliases (`Crompton`, `Crompton Greaves`, `CG Power`) to a single canonical entity, preventing misclassifications caused by regional brand names.

### 8.6 Technical Standards
* **Standards Crosswalk:** The schema recognizes equivalent standard specifications:
  * ASTM A312 TP304 is equivalent to ASME SA312 TP304.
  * IS 1554 Part 1 corresponds to IEC 60502 for low-voltage cables.
  * BS 5351 aligns with ISO 17292 for ball valves.
* **Direct Match Feature:** When two records declare identical governing standards, the ML model gives a positive weighting to this verification signal.

### 8.7 Material Grade
* **Metallurgical Equivalence:** The schema links metallurgical grades using international cross-reference maps:
  * Austenitic Stainless Steel: `SS304` = `AISI 304` = `1.4301` = `SUS 304`.
  * Fastener Carbon Steel: `Grade 8.8` = `Class 8.8` = `IS 1367 Part 3 Grade 8.8`.
* Conflicting grades (e.g., `SS304` vs `SS316`) trigger hard negative penalties, preventing catastrophic misclassification in corrosive or high-temperature applications.

### 8.8 Size / Dimension Compatibility
* **Dual Metric / Imperial Alignment:** In Indian industrial procurement, imperial and metric units coexist continuously:
  * `50 NB` = `2 Inch` = `60.3 mm OD`
  * `100 NB` = `4 Inch` = `114.3 mm OD`
* The canonical schema calculates and populates both representations in the attribute payload. This guarantees that an Indian Railways record using metric `50 NB` matches an ONGC offshore record using imperial `2 Inch`.

---

## 9. Database Planning Notes (Supabase / PostgreSQL)

The canonical schema is designed for implementation on **Supabase PostgreSQL** utilizing relational constraints, JSONB GIN indexing, and the `pgvector` extension. Below are architectural planning notes for future table creation.

### 9.1 `source_materials` Table
* **Role:** Stores all raw and normalized items ingested from CPSE ERPs.
* **Primary Key:** `id UUID DEFAULT gen_random_uuid()`.
* **Foreign Keys:**
  * `ingestion_batch_id REFERENCES ingestion_batches(id) ON DELETE CASCADE`.
* **Key Columns:**
  * `source_cpse VARCHAR(100) NOT NULL`
  * `source_system VARCHAR(100) NOT NULL`
  * `source_material_code VARCHAR(120) NOT NULL`
  * `raw_description TEXT NOT NULL`
  * `cleaned_description TEXT NOT NULL`
  * `standard_description TEXT NOT NULL`
  * `category VARCHAR(120) NOT NULL`
  * `sub_category VARCHAR(120) NOT NULL`
  * `material_type VARCHAR(120)`
  * `material_grade VARCHAR(100)`
  * `manufacturer VARCHAR(150)`
  * `part_number VARCHAR(120)`
  * `model_number VARCHAR(120)`
  * `uom VARCHAR(20) NOT NULL`
  * `attributes JSONB NOT NULL DEFAULT '{}'::jsonb`
  * `normalized_tokens TEXT[] NOT NULL DEFAULT '{}'`
  * `match_status VARCHAR(40) NOT NULL DEFAULT 'UNPROCESSED'`
  * `approval_status VARCHAR(40) NOT NULL DEFAULT 'PENDING_INGESTION'`
  * `created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`
  * `updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`
* **Indexes Planned:**
  * Unique index: `UNIQUE(source_cpse, source_material_code)` to prevent re-ingestion collisions.
  * GIN index on `attributes` (`USING gin (attributes jsonb_path_ops)`).
  * GIN index on `normalized_tokens` (`USING gin (normalized_tokens)`).
  * B-tree index on `(category, sub_category)`.
  * B-tree index on `match_status`.

### 9.2 `national_materials` Table
* **Role:** Houses the authoritative, canonical National Master Catalog.
* **Primary Key:** `id UUID DEFAULT gen_random_uuid()`.
* **Key Columns:**
  * `national_material_code VARCHAR(60) UNIQUE NOT NULL`
  * `standard_description TEXT NOT NULL`
  * `category VARCHAR(120) NOT NULL`
  * `sub_category VARCHAR(120) NOT NULL`
  * `material_type VARCHAR(120) NOT NULL`
  * `material_grade VARCHAR(100)`
  * `standard_uom VARCHAR(20) NOT NULL`
  * `canonical_attributes JSONB NOT NULL DEFAULT '{}'::jsonb`
  * `classification_path VARCHAR(255) NOT NULL`
  * `embedding vector(384)` (from `sentence-transformers/all-MiniLM-L6-v2`)
  * `status VARCHAR(40) NOT NULL DEFAULT 'ACTIVE'`
  * `created_by VARCHAR(100) NOT NULL`
  * `approved_by VARCHAR(100)`
  * `created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`
  * `updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`
* **Indexes Planned:**
  * HNSW Vector index on `embedding` (`USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64)`).
  * Unique B-tree index on `national_material_code`.
  * GIN index on `canonical_attributes`.
  * B-tree index on `classification_path`.

### 9.3 `material_mappings` Table
* **Role:** Represents the link connecting a legacy CPSE record to a National Master record.
* **Primary Key:** `id UUID DEFAULT gen_random_uuid()`.
* **Foreign Keys:**
  * `source_material_id REFERENCES source_materials(id) ON DELETE CASCADE`
  * `national_material_id REFERENCES national_materials(id) ON DELETE CASCADE`
* **Key Columns:**
  * `confidence_score NUMERIC(5,4) NOT NULL`
  * `match_method VARCHAR(50) NOT NULL`
  * `match_explanation JSONB NOT NULL DEFAULT '{}'::jsonb`
  * `approval_status VARCHAR(40) NOT NULL DEFAULT 'PENDING_L1'`
  * `reviewer_id VARCHAR(100)`
  * `reviewed_at TIMESTAMPTZ`
  * `created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`
* **Indexes Planned:**
  * Unique constraint: `UNIQUE(source_material_id, national_material_id)` to prevent duplicate links.
  * B-tree index on `(approval_status, confidence_score DESC)`.
  * B-tree index on `national_material_id`.

### 9.4 `material_attributes` Table (Attribute Dictionary & Metadata)
* **Role:** Canonical parameter registry defining valid schema keys, data types, validation regexes, and acceptable measurement units per category.
* **Primary Key:** `id UUID DEFAULT gen_random_uuid()`.
* **Key Columns:**
  * `category VARCHAR(120) NOT NULL`
  * `sub_category VARCHAR(120) NOT NULL`
  * `attribute_key VARCHAR(100) NOT NULL`
  * `display_name VARCHAR(150) NOT NULL`
  * `data_type VARCHAR(50) NOT NULL` (e.g., `NUMERIC`, `STRING`, `BOOLEAN`, `ENUM`)
  * `allowed_units TEXT[]` (e.g., `["mm", "inch", "m"]`)
  * `is_mandatory BOOLEAN NOT NULL DEFAULT FALSE`
  * `is_critical_for_matching BOOLEAN NOT NULL DEFAULT FALSE`
  * `validation_rule JSONB`
* **Indexes Planned:**
  * Unique constraint: `UNIQUE(category, sub_category, attribute_key)`.

### 9.5 `ingestion_batches` Table
* **Role:** Tracks batch uploads, raw files, provenance, and data processing states.
* **Primary Key:** `id UUID DEFAULT gen_random_uuid()`.
* **Key Columns:**
  * `batch_code VARCHAR(100) UNIQUE NOT NULL`
  * `source_cpse VARCHAR(100) NOT NULL`
  * `file_name VARCHAR(255) NOT NULL`
  * `file_hash_sha256 VARCHAR(64) NOT NULL`
  * `total_records INTEGER NOT NULL DEFAULT 0`
  * `processed_records INTEGER NOT NULL DEFAULT 0`
  * `status VARCHAR(50) NOT NULL DEFAULT 'PENDING'` (`INGESTING`, `SANITIZING`, `MATCHING`, `COMPLETED`, `FAILED`)
  * `error_summary JSONB DEFAULT '{}'::jsonb`
  * `uploaded_by VARCHAR(100) NOT NULL`
  * `started_at TIMESTAMPTZ DEFAULT NOW()`
  * `completed_at TIMESTAMPTZ`

### 9.6 `approval_workflows` Table
* **Role:** Manages the multi-tier review queue for material mappings and national SKU creations.
* **Primary Key:** `id UUID DEFAULT gen_random_uuid()`.
* **Foreign Keys:**
  * `mapping_id REFERENCES material_mappings(id) ON DELETE CASCADE`
* **Key Columns:**
  * `current_tier VARCHAR(20) NOT NULL DEFAULT 'TIER_1'` (`TIER_1_NODAL`, `TIER_2_MINISTRY`)
  * `tier_1_reviewer VARCHAR(100)`
  * `tier_1_decision VARCHAR(30)` (`APPROVED`, `REJECTED`, `ESCALATED`)
  * `tier_1_comments TEXT`
  * `tier_1_actioned_at TIMESTAMPTZ`
  * `tier_2_reviewer VARCHAR(100)`
  * `tier_2_decision VARCHAR(30)` (`APPROVED`, `REJECTED`, `MODIFIED`)
  * `tier_2_comments TEXT`
  * `tier_2_actioned_at TIMESTAMPTZ`
  * `created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`

### 9.7 `audit_logs` Table
* **Role:** Immutable, cryptographically verifiable security log tracking all mutations, approvals, and data access.
* **Primary Key:** `id UUID DEFAULT gen_random_uuid()`.
* **Key Columns:**
  * `timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW()`
  * `actor_id VARCHAR(150) NOT NULL`
  * `actor_role VARCHAR(100) NOT NULL`
  * `actor_organization VARCHAR(100) NOT NULL`
  * `action VARCHAR(100) NOT NULL` (e.g., `MAPPING_AUTO_APPROVED`, `MANUAL_OVERRIDE`, `NATIONAL_CODE_GENERATED`)
  * `target_entity_type VARCHAR(100) NOT NULL` (`source_material`, `national_material`, `material_mapping`)
  * `target_entity_id UUID NOT NULL`
  * `previous_state JSONB`
  * `new_state JSONB`
  * `payload JSONB`
  * `sha256_hash VARCHAR(64) NOT NULL` (Hash chaining previous row for tamper detection)
* **Indexes Planned:**
  * Append-only table enforced via PostgreSQL trigger (preventing `UPDATE` or `DELETE`).
  * B-tree index on `(target_entity_type, target_entity_id)`.
  * B-tree index on `timestamp DESC`.

---

## 10. Implementation Boundary & Compliance Notice

In strict accordance with the prototype planning requirements:
1. **Zero Database Migrations Executed:** No database migration files (e.g., Flyway, Liquibase, Alembic, or Supabase migration scripts) have been generated or run in this step.
2. **Zero Backend Models Created:** No ORM models (SQLAlchemy, Pydantic, Prisma, or Django models) have been added to the application codebase in this step.
3. **Zero AI Matching Logic Implemented:** No matching algorithms, scoring scripts, or embedding pipelines have been implemented in this step.
4. **Pure Documentation & Schema Architecture:** This document constitutes the foundational architectural plan and contract guiding subsequent implementation phases.
