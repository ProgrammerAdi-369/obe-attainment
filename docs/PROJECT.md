# OBE Attainment Calculation System: Project Documentation

Oct 3, 2026 · @Nir · Revision 2, updated after faculty meeting 2 (changes listed in section 15)

## 1. Overview

This project replaces a manual, Excel-based Outcome-Based Education (OBE) calculation with a pipeline that turns student marks into Course Outcome (CO) and Program Outcome (PO/PSO) attainment for a whole batch, and produces the attainment report the faculty needs.

**Problem today.** For a batch (for example 2022–26), every student takes about 52 courses over four years. Each course has COs, several assessment tools (CCA, assignment, PBL, mid-term, lab assessment) and an end-term exam. Course teachers compute CO attainment by hand in one Excel workbook per course; the sample provided is System Software and Compiler Design (CET3011B), final year B.Tech CSE, AY 2025-26, with 291 students. The course coordinator then consolidates the results into Tables A to F. The workbook contains hand-typed values and broken references (#REF!), so results are hard to repeat, check or compare across batches.

**Goals**

- Compute CO attainment per student, per course, from raw marks with no manual calculation.
- Compute PO and PSO attainment per student across all four years, and per batch against a target.
- Keep structure, marks and results in a PostgreSQL database so batches can be compared later.
- Accept all inputs as Excel uploads, so that no one types data in by hand.
- Produce a master Excel report and a faculty-ready report as the main output.

**Glossary**

| Term | Meaning in this project |
| --- | --- |
| CO | Course Outcome. A course has about 5 (CO1 to CO5), defined in its syllabus. |
| PO / PSO | Program Outcomes (PO1 to PO12) and Program Specific Outcomes (PSO1 to PSO3). |
| CCA | Continuous Comprehensive Assessment: internal theory tools such as assignment, PBL (active learning) and mid-term. 30 marks in the sample. |
| LCA | Lab Continuous Assessment: marks for lab assignments. 30 marks in the sample. |
| End-term | The end-term exam, 40 marks, converted to 100. It is not mapped to a single CO; it counts equally for all COs. |
| Direct attainment | CO attainment computed from student marks (60% internal, 40% end-term). |
| Indirect attainment | CO attainment from the end-course survey: the percentage of students answering Yes. |
| Total actual attainment | 80% direct plus 20% indirect. |
| Target | The CO target percentage that each course teacher gives for each CO before the course starts (Form 8 of the course file). It is a user input, not part of the syllabus. Also the PO target derived from the CO-PO mapping. |
| CO level | Level 3, 2 or 1 derived from the direct attainment percentage and the CO target: 3 when the target is met, 2 from 50% up to the target, 1 below 50% (section 8, step 4). The scale is fixed and hardcoded. |
| Mapping strength | The 0 to 3 value (L=1, M=2, H=3) that links a CO to a PO or PSO. |
| Gap | Target minus actual attainment. A positive gap needs an action plan (Table B). |
| IQAC | Internal Quality Assurance Cell, the receiver of the batch comparison reports in phase 2. |

## 2. Scope and phasing

Phase 1 delivers a working calculation pipeline and the report for one batch; phase 2 adds comparison across batches and gap analysis for IQAC.

| Area | Phase 1 (this build) | Phase 2 (later) |
| --- | --- | --- |
| Data | PostgreSQL database for students, courses, COs, tools, marks, mappings, results | Multi-batch history and comparison |
| Input | Excel uploads in the layout of the course workbook (section 7) | Direct feeds from admission, result extraction and the curriculum system |
| Attainment | Direct attainment: CO per student and per class, PO and PSO per course (Tables A, B, E, F) | Indirect attainment from the end-course survey, so that the 80/20 total is applied (open item O10) |
| Output | Master Excel and faculty report | Batch-to-batch reports and suggested changes for IQAC |
| Access | Teacher login with full rights | Review roles if needed |
| Interface | No front end; upload, run and download through a backend API or command line | Optional web UI |
| Rubrics | Tool marks per CO are fixed by the syllabus and loaded as course configuration; teachers cannot change them | A changed syllabus is loaded as a new rubric version, so old batches keep their old weights |

**Out of scope for phase 1:** the survey analysis for indirect attainment, a graphical interface, admin or HOD roles, and automatic feeds from other university systems. The 80/20 formula and a survey table are already in the design (sections 8 and 9), so indirect attainment can be switched on without a redesign.

## 3. Users and access

There is one role, Teacher. Every teacher logs in and has full rights to configure and run the system; there is no admin or HOD role in phase 1.

Two duties are done by teachers, but they are duties and not permissions:

| Duty | Who does it | What it covers in the system |
| --- | --- | --- |
| Course teacher | The teacher assigned to a course | Uploads marks and the final CO-PO mapping; supplies the lab assignments with their COs (Table 3) and the CO targets (Table A) before the course starts; reviews class CO attainment and levels; records reasons and action plans for gaps (Table B) |
| Course coordinator | A teacher marked as coordinator for a course | Decides the CO-PO mapping together with the course teachers, collects the CO targets from the course teachers and enters them, triggers the run, reviews the consolidated tables (C, D, E, F) and issues the final tables back to course teachers |

**Consequence of full rights.** Because any teacher can change any configuration, the system records who changed what and when (audit log), and every calculation run stores a snapshot of the configuration it used. Results can then always be traced and reproduced.

## 4. Current manual process and Tables A to F

The course workbook has three working tabs and a survey tab; the system generates every calculated table from stored data and keeps the teacher-written text in the database.

**Workbook structure**

| Tab | Content | In the system |
| --- | --- | --- |
| 1. CO-PO mapping and hours | Seven small tables: (1) CO to PO/PSO ticks, (2) theory hours per unit and CO, (3) lab assignments and their CO, (4) hours per CO, (5) rule for mapping strength from hours, (6) baseline mapping strengths, (7) final mapping by teachers' judgement | Tables 1 and 2 are given and table 3 is the initial input; tables 4 to 6 are generated (the rule in table 5 is fixed and hardcoded); table 7 is the mapping used in calculation |
| 2. Weight calculation | Tool marks per CO and the percentage weight of each tool in each CO | Tool marks per CO are fixed by the syllabus; the LCA split is generated from table 3; the marks-per-CO table is intermediate and not shown; the percentage weights are the output |
| 3. Attainment calculation | Step 1 raw marks per student, step 2 weighted marks, step 3 CO attainment (60% internal, 40% end-term), then Tables A, B and F | Computed; steps 1 and 2 (copying marks, then weighting them) become one calculation |
| Survey | End-course survey questions linked to COs (Yes, Maybe, No) | Phase 2 input |

**The six result tables**

| Table | Content in the workbook | Prepared by | In the system |
| --- | --- | --- | --- |
| A | CO target attainment per CO (Form 8 of the course file), given by the course teachers, and the CO level scale 3, 2, 1 | Course teachers (targets); the level scale is fixed | Targets are a user input per course; the level scale is hardcoded |
| B | CO gap analysis: direct %, indirect %, total actual %, levels, status Attained or Not attained; teachers add reasons and action plan for gaps. In phase 1 it shows the direct % and Attained or Not attained, with the level | Course teacher | Generated; reason and action plan entered by the teacher |
| C, D | Consolidations of direct and indirect results across teachers; their layout is not in the workbook | Course coordinator | Open item O1 |
| E | Overall CO attainment of the course: the average of the CO levels (2.84 in the sample) | Course coordinator | Generated |
| F | Target and actual attainment of each PO and PSO for the course | Course coordinator | Generated |

**Existing hand-off.** The coordinator collects results from all teachers, prepares C, D, E and F, and returns A, C, D, E and F to each teacher for their attainment sheet. With a shared database this collection step disappears: all teachers work on the same data, and the coordinator only triggers the run and reviews the output.

### Data flow confirmed in faculty meeting 2

The second meeting went through the workbook tab by tab and settled which tables are given, which are inputs, which are fixed and which are generated. The CO is the primary key in every table, and the unit links the theory and lab tables. The CO calculation up to Table B was covered; the indirect part and the PO side (Tables E and F) follow in later meetings.

| Tab | Table or step | Role | How it is produced |
| --- | --- | --- | --- |
| 1 | Tables 1 and 2: CO-PO ticks, theory hours per unit and CO | Given | Course set-up; the theory part is fixed |
| 1 | Table 3: lab assignments with unit and CO | Initial input | Varies by course; supplied by the user |
| 1 | Table 4: hours per CO | Generated | From Tables 2 and 3 |
| 1 | Table 5: hours-to-strength rule | Fixed | Hardcoded: more than 30% is 3, 16 to 29% is 2, 5 to 15% is 1, below 5% is 0 |
| 2 | Tool marks per CO for the CCA tools (for example 15 and 5 for the tool maximums) | Given, fixed | Set by the syllabus; nobody can change them |
| 2 | LCA marks per CO | Generated | From Table 3: each assignment weighs 1/N and the weights of the same CO are added |
| 2 | Marks each tool carries per CO | Intermediate | Calculated and stored; not shown to the user |
| 2 | Weight of each tool per CO, in percent | Generated, shown | Last table of Tab 2; each CO adds up to 100 |
| 3 | Student marks | Input | Marks upload |
| 3 | Internal score per CO and CO attainment | Generated | Marks times weights in one calculation, internal at 60% and end-term at 40% |
| 3 | Class average per CO | Generated | Average over all students |
| 3 | Table A: CO targets | Input | One target per CO from each teacher; the levels 3, 2, 1 are hardcoded |
| 3 | Table B: direct attainment | Generated | Direct % and Attained or Not attained, with the level |

## 5. Functional requirements

The system must let a teacher load data, run the calculation, and download results, with no manual calculation step in between.

| ID | Requirement | Priority |
| --- | --- | --- |
| FR-01 | Teacher registers and logs in with credentials; all data-changing actions require login. | Must |
| FR-02 | Upload a student list (unique student identifier, name, batch) from Excel; validate and store it. | Must |
| FR-03 | Upload the course set-up: course header, COs, units with theory hours and CO (Tables 1 and 2, given), and the lab assignments with unit, CO and hours (Table 3, the initial input). | Must |
| FR-04 | Load the assessment tools per course (assignment, PBL, mid-term, MCQ, attendance, LCA, end-term) with maximum marks and the marks each tool carries for each CO, as fixed by the syllabus. Teachers cannot change them. | Must |
| FR-05 | Upload marks per student per tool from Excel, including end-term out of 40. | Must |
| FR-06 | Upload the CO-PO/PSO mapping: the √ or 0 table and the final mapping strengths (0 to 3) set by the teachers. | Must |
| FR-07 | Reject bad uploads with a row-level error report (unknown student, marks above maximum, CO weights not adding to 100) and never half-load a file. | Must |
| FR-08 | Compute the percentage weight of each tool in each CO; for the LCA, generate the split from Table 3 (1/N per assignment, added up per CO). The marks-per-CO table behind the weights is an intermediate result and is not shown. | Must |
| FR-09 | Compute each student's internal CO score in one calculation (marks times weights), then CO attainment as 60% internal plus 40% end-term. A tool that carries no marks for a CO contributes 0 to it. | Must |
| FR-10 | Compute class CO attainment (average of student values), the CO level from the fixed 3, 2, 1 rule against the CO target (Table A, entered by the teacher), and the direct attainment % with Attained or Not attained (Table B). | Must |
| FR-11 | Compute hours per CO (theory plus lab) and suggest a baseline mapping strength from the hours rule; teachers confirm or change it to give the final mapping. | Should |
| FR-12 | Compute overall CO attainment (Table E) and PO and PSO target, actual and gap (Table F). | Must |
| FR-13 | Flag COs and POs with a gap and let the teacher record reason and action plan. | Should |
| FR-14 | Compute per-student PO and PSO attainment, and the roll-up across courses for a batch (open item O9). | Should |
| FR-15 | Produce the master Excel in the layout of the course workbook, plus a faculty report per course. | Must |
| FR-16 | Keep every run with its configuration snapshot and results, so a past run can be reopened or compared. | Must |
| FR-17 | Make CO targets and the course structure (units, lab assignments, tools) configurable per course without code changes. The level scale, the hours-to-strength rule and the 60/40 split are fixed global values in one config file. | Must |
| FR-18 | Re-run safely: uploading corrected marks and recalculating replaces results without duplicating data. | Should |
| FR-19 | When survey data is supplied, apply the 80/20 total and combined level; until then indirect weight is 0. | Could |

## 6. Non-functional requirements

Correctness and traceability matter more than speed, because the results feed accreditation-style reports.

| Area | Requirement |
| --- | --- |
| Accuracy | Results for the sample course (CET3011B, 291 students) must reproduce the workbook's student CO values for CO1, CO3 and CO5 within 0.1 for all 291 students. Where the workbook itself is inconsistent (section 13), the difference is explained and signed off before release. |
| Reproducibility | Same data and same configuration always give the same results. Each run stores its configuration snapshot. |
| Traceability | Every attainment value can be traced back to the marks, weights and mappings that produced it. |
| Security | Passwords stored hashed (bcrypt or argon2); authenticated access only; student names and identifiers not written to logs. |
| Auditability | Changes to configuration, mappings and uploads are logged with teacher, time and old and new value. |
| Data integrity | Foreign keys, unique constraints and transactions in PostgreSQL; an upload either loads fully or not at all. |
| Performance | A course of about 300 students runs in seconds; a full batch (about 52 courses) completes in minutes on a normal server. |
| Maintainability | Calculation logic isolated from the database and the API, covered by automated tests with the sample course as the first test case. |
| Configurability | Targets and the course structure are data per course. The level scale, the hours-to-strength rule and the 60/40 split are fixed values held in one config file, never in code. |
| Backup | Daily database backup; reports can be regenerated from stored data. |

## 7. Input data and Excel templates

All data enters through Excel templates that follow the layout of the course workbook, so teachers fill in what they already know. No one types data into the system.

| Template | Source | Columns |
| --- | --- | --- |
| 1. Students | Admission team | student\_id (roll number or PRN, open item O6), student\_name, program, batch |
| 2. Course and COs | Course teacher | course\_code, course\_name, class, semester, academic\_year, co\_code, co\_description |
| 3. Units and hours (Table 2) | Course teacher | unit\_no, theory\_hours, co\_codes (one or more) |
| 4. Lab assignments (Table 3), the initial input | Course teacher | assignment\_no, name, unit\_no, co\_codes, lab\_hours (open item O5) |
| 5. CO-PO ticks (Table 1) | Course coordinator | co\_code, PO1 to PO12, PSO1 to PSO3, each √ or 0 |
| 6. Final CO-PO mapping (Table 7) | Course coordinator | co\_code, PO1 to PO12, PSO1 to PSO3, each 0 to 3 |
| 7. Assessment tools and CO allocation (Tab 2) | Syllabus (fixed; teachers cannot change it) | tool\_name, category (CCA, LCA, END\_TERM), max\_marks, marks\_for\_CO1 to marks\_for\_CO5 |
| 8. Marks (Step 1) | Result extraction | student\_id, one column per tool (assignment, PBL, mid-term, MCQ, attendance, LCA, end-term out of 40) |
| 9. CO targets (Table A) | Course teacher (collected by the coordinator) | co\_code, target\_pct |
| 10. End-course survey | Course teacher | co\_code, yes\_count, maybe\_count, no\_count (phase 2) |

**Rules applied on upload**

- Every student identifier and course code must already exist or be in the same upload.
- Marks must be between 0 and the tool's maximum; the sample has no marker for absent students (open item O7).
- Tool maximums for the internal tools must add up to 60 (30 CCA plus 30 LCA in the sample) and the end-term is out of 40.
- For every CO, the tool weights computed from the allocation must add up to 100.
- Ticks in template 5 are read as 1; blank or 0 as 0. Table 7 values must be 0, 1, 2 or 3.
- Re-uploading the same file replaces the earlier load for that batch and course rather than adding to it.

### MVP: what is hardcoded and what is uploaded

In the MVP only one file is uploaded, the marks workbook; everything else for the sample course is hardcoded in versioned configuration files (YAML) that are validated when the system starts. Hardcoded means kept in a config file and not inside the calculation code, so each item can later become an upload template without changing the engine.

| Item | MVP | Becomes an input later |
| --- | --- | --- |
| Marks: student id, name, assignment, PBL, mid-term, LCA, end-term out of 40 | **Uploaded** (Excel or CSV, one row per student) | Stays an upload (template 8) |
| Student list | Taken from the marks file until the real identifier is known (O6) | Template 1 from the admission team |
| Program, batch, course header (CET3011B, B.Tech CSE, Semester VIII, AY 2025-26) | Hardcoded in the course YAML | Templates 1 and 2 |
| COs and descriptions | Hardcoded (CO1 to CO5) | Template 2 |
| Unit hours and lab assignments with hours (Tables 2 and 3; lab hours 3, 3, 4, 4, 4, 4, 4, 4 from open item O5) | Hardcoded in the course YAML; Table 3 is the initial input of a course | Templates 3 and 4 |
| CO-PO ticks (Table 1) and final mapping strengths (Table 7) | Hardcoded; the baseline from hours (Tables 4 to 6) is computed for information only | Templates 5 and 6 |
| Assessment tools, maximum marks and marks per CO (assignment 5, PBL 10, mid-term 15, LCA 30, end-term 40) | Hardcoded from the syllabus; fixed, teachers cannot change them | Template 7 (still from the syllabus) |
| CO targets (60, 50, 55, 50, 50 in the sample) | User input per CO from each teacher; in the MVP written in the course YAML | Template 9 |
| Rules: 60/40 internal and end-term, end-term ×2.5 and equal for all COs, LCA split by assignment count, level scale (3 at or above the target, 2 from 50 up to the target, 1 below 50), hours-to-strength rule, equal split for multi-CO units, absent as 0 | Hardcoded in one global rules file | Stays fixed; changed only by editing the global rules file, not per course |
| 80/20 direct and indirect | Built in, with indirect weight 0 (open item O10) | Template 10 (survey counts) |
| PO1 to PO12 and PSO1 to PSO3 | Hardcoded seed list (codes) | Edited by teachers if the program changes |
| Teacher accounts | Two or three seeded accounts with hashed passwords from environment variables | Registration screen or endpoint |
| Table B reasons and action plans | Empty columns in the Excel report that teachers fill in by hand | Entered through the API and stored in the database |

The course YAML has the shape of the sample workbook, so a second course is added by writing another file, with no code change. The extraction of the marks file from the sample workbook is a one-off script.

## 8. Calculation methodology

Attainment is computed in seven steps that follow the workbook; the formulas below reproduce the sample course (CET3011B, 291 students) for CO1, CO3 and CO5, while CO2, CO4 and the typed class averages in the workbook do not follow them (open items O2 and O12). The system keeps full precision.

**Notation.** Student i, CO j, tool t, PO or PSO p. M\_t is the maximum marks of tool t, x\_it the marks the student got, m\_tj the marks tool t carries for CO j, and w\_tj the weight of tool t in CO j.

### Step 1. Weight of each tool in each CO (Tab 2)

For CCA tools (assignment, PBL, mid-term) the syllabus fixes m\_tj, and neither teachers nor the coordinator can change it. The 30 LCA marks are split by the lab assignments of Table 3: each of the N assignments weighs 1/N, and the weights of the assignments mapped to the same CO are added, so a CO that appears n\_j times gets n\_j/N of the 30 marks (CO3 appearing 4 times in 8 assignments gets 4/8). The table of marks per tool and CO that results is an intermediate table: it is stored but not shown to the user. The weight is the tool's share of the CO's marks as a percentage, so each CO adds up to 100, and this percentage table is the output of the step.

```latex
w_{tj} = 100 \cdot \frac{m_{tj}}{\sum_t m_{tj}} \qquad m_{\text{LCA},j} = 30 \cdot \frac{n_j}{N}
```

### Step 2. Student internal score for each CO

```latex
I_{ij} = \sum_t \frac{x_{it}}{M_t}\, w_{tj}
```

Each tool contributes the student's fraction of its maximum marks times the tool's weight in that CO. The result is on a 0 to 100 scale.

This is one calculation: the weight is applied to the marks directly, so there is no separate step that first copies each student's marks into a table per CO. A tool that carries no marks for a CO has weight 0 and contributes 0 to that CO's internal score, whatever the student scored in it (for example PBL for CO1 and CO2). The workbook copied the PBL marks into the CO1 and CO2 columns; the faculty confirmed that the value there must be 0, and that copy step is dropped.

### Step 3. Student CO attainment (60% internal, 40% end-term)

```latex
A_{ij} = 0.6\, I_{ij} + 0.4\, E_i \qquad E_i = 100 \cdot \frac{\text{end-term marks}}{40}
```

The end-term is not split by CO: the same E\_i is used for every CO. The 60 internal marks are converted to 60% and the 40 end-term marks are taken as they are as 40%, so 0.4 E\_i is simply the end-term marks out of 40. In the meeting the faculty described the end-term as questions of 5 marks for CO1, 5 marks for CO2 and 30 marks for CO3 to CO5, and then took the full 40 marks for every CO; the equal treatment of the workbook is kept (open item O14).

### Step 4. Class CO attainment, level and status (Tables A and B)

Class attainment is the average of the student values.

```latex
D_j = \frac{1}{n} \sum_i A_{ij}
```

The CO target T\_j in Table A is a user input: each course teacher gives the target for every CO before the course starts (60, 50, 55, 50 and 50 in the sample). It is not in the syllabus and it is not hardcoded. The level scale 3, 2, 1 is fixed and hardcoded in the global rules file, and the level follows from D\_j and T\_j (working reading of the faculty's description, open item O13):

| D\_j (class average %) | CO level | Status in Table B |
| --- | --- | --- |
| T\_j or more | 3 (High) | Attained |
| 50 to below T\_j | 2 (Medium) | Not attained |
| Below 50 | 1 (Low) | Not attained |

The floor of 50 is a fixed value in the rules file. When T\_j is 50 or lower, level 2 does not occur. This replaces the fixed 60/50/40 thresholds of the earlier version, and there is no level 0 any more. In phase 1 Table B shows D\_j, the level and the status; the indirect and total columns are added with the survey (step 5).

### Step 5. Total actual attainment, status and overall CO attainment (Tables B and E)

The indirect value S\_j is the percentage of students answering Yes in the end-course survey. The total is 80% direct plus 20% indirect, and it is compared with the CO target of Table A.

```latex
\text{Total}_j = 0.8\, D_j + 0.2\, S_j \qquad F_j = 0.8\, L^{D}_j + 0.2\, L^{I}_j \qquad E_{\text{course}} = \operatorname{mean}_j F_j
```

The status is Attained when Total\_j is at least the CO target. L^D is the level of D\_j from step 4 and L^I the level of S\_j (how the indirect value is levelled is still to be explained by the faculty, open item O10); F\_j is the final CO level and E\_course the overall CO attainment of the course (Table E). In phase 1 the indirect weight is 0, so Total\_j = D\_j and F\_j = L^D\_j.

### Step 6. Mapping strength from instruction hours (Tables 4 to 7)

Hours of a CO are its theory hours (Table 2) plus the hours of its lab assignments (Table 3, the input), generated as Table 4. The CO is the primary key. The share of total hours gives a baseline mapping strength:

```latex
\text{share}_j = 100 \cdot \frac{h_j}{\sum_k h_k}
```

| Share of total hours | Strength |
| --- | --- |
| More than 30% | 3 (H) |
| 16 to 29% | 2 (M) |
| 5 to 15% | 1 (L) |
| Below 5% | 0 |

The bands are fixed and hardcoded; they are not an input. The baseline is the tick table (Table 1) multiplied by this strength (Table 6). The teachers then adjust it by judgement into the final CO-PO mapping (Table 7), and only the final table is used in the calculation. The system proposes the baseline and the teacher confirms it.

### Step 7. PO and PSO target, actual and gap (Table F)

Meeting 2 stopped at the direct CO attainment in Table B. Table E and this step are to be walked through with the faculty in a later meeting and stay as designed. Their numbers move with the new level rule of step 4, because they use the CO levels.

With g\_jp the final mapping strength of CO j for PO p:

```latex
\text{Target}_p = \operatorname{mean}_{j:\,g_{jp}>0}\, g_{jp} \qquad \text{Actual}_p = \text{Target}_p \cdot \frac{E_{\text{course}}}{3} \qquad \text{Gap}_p = \text{Target}_p - \text{Actual}_p
```

Only non-zero entries enter the target average. A positive gap marks the PO for an action plan.

**Student and batch level (open item O9).** The workbook works at class level. For a single student over four years, as asked in the meeting, the same step 7 is applied with the student's own overall CO attainment (the average of the levels of that student's A\_ij), and each PO is then averaged over the courses where its target is non-zero.

### Worked example from the sample course

Weights from Step 1. In each cell the marks are the intermediate table (not shown in the report) and the percentage is the output:

| CO | Assignment (/5) | PBL (/10) | Mid-term (/15) | LCA (/30) | CO total |
| --- | --- | --- | --- | --- | --- |
| CO1 | 3 (17.14%) | 0 | 7 (40%) | 7.5 (42.86%) | 17.5 |
| CO2 | 2 (11.43%) | 0 | 8 (45.71%) | 7.5 (42.86%) | 17.5 |
| CO3 | 0 | 5 (25%) | 0 | 15 (75%) | 20 |
| CO4 | 0 | 2 (100%) | 0 | 0 | 2 |
| CO5 | 0 | 3 (100%) | 0 | 0 | 3 |
| Total | 5 | 10 | 15 | 30 | 60 |

Student with serial number 1 scored assignment 3/5, PBL 3/10, mid-term 6/15, LCA 12/30 and end-term 22/40, so E = 55.

- CO1: I = 3/5 × 17.14 + 6/15 × 40 + 12/30 × 42.86 = 10.29 + 16 + 17.14 = 43.43, so A = 0.6 × 43.43 + 0.4 × 55 = 48.06 (the workbook shows 48.04 because it rounds the weights).
- CO3: I = 3/10 × 25 + 12/30 × 75 = 7.5 + 30 = 37.5, so A = 0.6 × 37.5 + 0.4 × 55 = 44.5, as in the workbook.

Class results for 291 students, recomputed from the raw marks with the formulas above and compared with the workbook:

| CO | Target (%) | Class average from the formula (%) | Workbook Average row, typed (%) | Mean of the workbook's own student column (%) | Level on the formula value (step 4 rule) | Status |
| --- | --- | --- | --- | --- | --- | --- |
| CO1 | 60 | 58.65 | 60.85 | 58.63 | 2 | Not attained |
| CO2 | 50 | 57.15 | 48.54 | 51.55 | 3 | Attained |
| CO3 | 55 | 55.69 | 52.43 | 55.69 | 3 | Attained |
| CO4 | 50 | 55.16 | 40.47 | 46.71 | 3 | Attained |
| CO5 | 50 | 55.16 | 47.45 | 55.15 | 3 | Attained |

The formula reproduces the workbook's student values for CO1, CO3 and CO5 within 0.1 on all 291 students. For CO2 and CO4 the workbook applies smaller effective weights than its own Tab 2 (for student 1, CO4 internal is 22.5 where the weights give 30), and its typed Average row matches no column. The workbook's Table B (direct levels 3, 3, 3, 2, 3 and overall 2.84) therefore cannot be reproduced (open items O2 and O12).

For the PO step with the formula values, the levels are 2, 3, 3, 3, 3, so the direct-only overall attainment is 2.8. PO1 has target 3 and actual 3 × 2.8 / 3 = 2.8. PO8 has strengths 3, 3, 3, 2, 2, so target 2.6 and actual 2.6 × 2.8 / 3 = 2.43. With the workbook's 2.84 the same POs would give 2.84 and 2.46. (Under the earlier 60/50/40 thresholds all five COs were level 2, giving 2.0 and 1.73.)

## 9. Database design

The PostgreSQL schema has 31 tables in five groups: fixed structure, assessment configuration, marks, calculated results, and system tables. Structure rarely changes; marks and tool weights vary; results are always derived and can be rebuilt.

**A. Structure (fixed per batch)**

| Table | Purpose | Key columns |
| --- | --- | --- |
| teacher | Login accounts | teacher\_id, name, email, password\_hash |
| program | Degree program | program\_id, name |
| batch | A cohort, for example 2022–26 | batch\_id, program\_id, admission\_year, label |
| student | Students of a batch | student\_id, roll\_no or PRN (unique, open item O6), name, batch\_id |
| course | A course in the curriculum | course\_id, code, name, semester, class, program\_id |
| batch\_course | Which courses a batch takes in which semester and academic year | batch\_id, course\_id, semester, academic\_year |
| course\_teacher | Who teaches or coordinates a course for a batch | course\_id, batch\_id, teacher\_id, is\_coordinator |
| course\_unit | Units with theory hours (Table 2) | unit\_id, course\_id, unit\_no, theory\_hours |
| unit\_co\_map | Which COs a unit supports | unit\_id, co\_id, share (default equal) |
| course\_outcome | COs of a course with the target given by the course teacher | co\_id, course\_id, co\_code, description, target\_pct |
| lab\_assignment | Lab assignments (Table 3) | lab\_id, course\_id, assignment\_no, name, unit\_no, lab\_hours |
| lab\_co\_map | Which COs a lab assignment supports | lab\_id, co\_id |
| program\_outcome | PO1 to PO12 and PSO1 to PSO3 | po\_id, code, description, type (PO or PSO) |
| co\_po\_map | CO-PO/PSO mapping | co\_id, po\_id, tick (Table 1), baseline\_strength (Table 6), final\_strength 0 to 3 (Table 7) |

**B. Assessment configuration (varies by course and rubric version)**

| Table | Purpose | Key columns |
| --- | --- | --- |
| rubric\_version | A named set of tools and weights, so that rubrics can change later | rubric\_id, name, valid\_from |
| assessment\_tool | A tool in a course under a rubric | tool\_id, course\_id, rubric\_id, name, category (CCA, LCA, END\_TERM), max\_marks |
| tool\_co\_marks | Marks each tool carries for each CO (fixed by the syllabus; LCA derived from lab assignments). Intermediate: stored for traceability, not shown in reports | tool\_id, co\_id, allocated\_marks |
| tool\_co\_weight | Derived percentage weight of each tool in each CO (step 1) | tool\_id, co\_id, weight\_pct |
| attainment\_config | Fixed rules used by a course's runs: 60/40, 80/20, hours-to-strength thresholds, level floor 50. Values come from the global rules file and are the same for every course | course\_id, key, value |
| attainment\_level | Fixed CO level scale (Table A): level 3 at or above the CO target, level 2 from the floor up to the target, level 1 below the floor. Seeded from the rules file, not edited per course | course\_id, level, floor\_pct |
| co\_survey | End-course survey counts per CO (phase 2) | course\_id, co\_id, yes\_count, maybe\_count, no\_count |

**C. Marks**

| Table | Purpose | Key columns |
| --- | --- | --- |
| marks | One row per student per tool | student\_id, tool\_id, marks\_obtained, is\_absent |

**D. Calculated results (each row carries run\_id)**

| Table | Purpose | Key columns |
| --- | --- | --- |
| calc\_run | One calculation run with its configuration snapshot | run\_id, batch\_id, triggered\_by, started\_at, config\_snapshot |
| co\_hours\_summary | Hours per CO and baseline strength (Table 4) | run\_id, co\_id, theory\_hours, lab\_hours, share\_pct, strength |
| student\_co\_attainment | Steps 2 and 3 | run\_id, student\_id, co\_id, internal\_score, endterm\_score, total\_pct |
| class\_co\_attainment | Tables A, B and E (steps 4 and 5) | run\_id, co\_id, direct\_pct, direct\_level, indirect\_pct, total\_actual\_pct, final\_level, status |
| course\_po\_attainment | Table F (step 7) | run\_id, course\_id, po\_id, target, actual, gap |
| student\_po\_attainment | Per-student PO and PSO attainment (open item O9) | run\_id, student\_id, po\_id, attainment |

**E. System**

| Table | Purpose | Key columns |
| --- | --- | --- |
| gap\_action | Reason and action plan per flagged gap (Table B) | run\_id, co\_id or po\_id, reason, action\_plan, teacher\_id |
| upload\_log | Every upload, its type, status and errors | upload\_id, template, filename, teacher\_id, status, error\_report |
| audit\_log | Who changed what and when | audit\_id, teacher\_id, table\_name, record\_id, old\_value, new\_value, at |

**Relationships.** A batch has students and courses; a course has units, lab assignments, COs and tools; tools carry marks for COs; units and lab assignments support COs; marks link student and tool; COs map to POs with a strength. Results tables hang off calc\_run, so a batch can be recalculated and compared with earlier runs, which is the base for the phase 2 batch comparison. Tables C and D will be added once their content is confirmed (open item O1); they are expected to be views over these tables.

## 10. System architecture and tech stack

The system is a Python pipeline around one PostgreSQL database: Excel files go in through a validated upload, the calculation engine works only on stored data, and reports are generated from stored results.

&#91;embedded content: system architecture · 7 components, one database\]

Teachers log in, upload the templates, and the data is validated and loaded. The engine reads marks and configuration, writes results back, and the report generator builds the outputs from those results.

| Layer | Choice | Note |
| --- | --- | --- |
| Language | Python | Single language for ingestion, calculation and reports |
| Database | PostgreSQL, with SQLAlchemy and Alembic migrations | Schema in section 9 |
| Upload and validation | pandas and openpyxl | Templates from section 7; errors returned per row |
| Calculation | Pure Python module, independent of the database | Tested with pytest, starting with the worked example |
| Access | FastAPI backend with password login (hashed passwords, token sessions) and upload, run and download endpoints | Proposed; a command line is the fallback because the front end is not a goal |
| Reports | openpyxl or XlsxWriter for the Excel workbook; PDF export optional | Section 11 |

**Design rule.** The calculation code takes plain data in and returns plain results out, so the same logic can later be called from a web UI, a scheduled job or a notebook.

## 11. Report output specification

The report is the main deliverable: one master Excel workbook per batch, plus a short faculty report per course. Both are generated from the database and can be regenerated at any time.

| Sheet in the master workbook | Content |
| --- | --- |
| Summary | Course or batch, run date, configuration used, headline CO and PO attainment against target |
| CO-PO mapping | Tables 1 to 7: ticks, unit and lab hours, hours per CO, baseline and final mapping strengths |
| Tool weights | Percentage weight of each tool in each CO (Tab 2). The marks-per-CO table behind it is intermediate and not shown |
| Student steps | Per student: internal score per CO, end-term score and CO attainment (steps 1 to 3) |
| Table A | CO targets (teacher input) and the fixed level scale 3, 2, 1 |
| Table B | Direct %, level, Attained or Not attained (indirect % and total actual % are added when the survey is switched on), with reason and action plan entered by teachers |
| Tables C, D | Added after their content is confirmed (open item O1) |
| Table E | Overall CO attainment of the course |
| Table F | PO and PSO target, actual and gap |
| Student PO | One row per student: PO1 to PO12 and PSO1 to PSO3 (the master file for a batch, open item O9) |
| Config | Weights, targets, thresholds and mapping rules used by this run |

**Faculty report per course.** A short document with the CO list, tool weights, class CO attainment and levels, the gaps and the action plan. A PDF export is added if the faculty want it.

**Formulas in Excel.** The calculation runs in Python; the workbook shows values, and key sheets (class averages, Table B, Table F) carry Excel formulas so that faculty can trace and check them, which they asked for when reviewing the manual sheet.

## 12. Phased delivery plan

Delivery runs in sequence, and each phase ends with a check that must pass before the next one starts. No durations are given because the team size and dates are not yet known.

| Phase | Deliverables | Exit check |
| --- | --- | --- |
| 0. Clarify | Answers to open items O1 to O14; the two-dimensional input table that the faculty will prepare; real student identifiers; final Excel templates; list of inconsistencies in the sample workbook fixed | Faculty sign off on templates and formulas |
| 1a. Foundation | Database schema and migrations; teacher login; Excel upload with validation and error reports | A full course and a full batch load without manual fixes |
| 1b. Calculation | Engine for steps 1 to 7 with automated tests, starting with the sample course | Sample course (CET3011B, 291 students) reproduces the workbook's student CO values for CO1, CO3 and CO5 within 0.1, and every difference elsewhere (CO2, CO4, typed averages) is listed and signed off |
| 1c. Reports | Master Excel, faculty report per course, Table B entry, audit log | Faculty accept the report as a replacement for the manual workbook |
| 2. Comparison | Multi-batch comparison, gap analysis and suggested changes for IQAC; indirect attainment from the survey; optional web UI | Agreed with IQAC after phase 1 feedback |

## 13. Assumptions, risks and open items

The sample workbook settled five of the earlier open items and corrected four assumptions; fourteen points remain open (O13 and O14 were added in faculty meeting 2), and the design uses the working answer in each row until the faculty decide.

**Resolved or corrected by the sample workbook**

| Earlier assumption | What the workbook shows |
| --- | --- |
| The 80-20 weight is unclear | It is 80% direct plus 20% indirect (survey percentage of Yes). The 60/40 internal and end-term split is a separate rule inside the direct calculation. |
| CO target and level thresholds are placeholders | The target is set per CO from Form 8 (60, 50, 55, 50, 50 in the sample). The workbook levels were 60% or more is 3, 50–59% is 2, 40–49% is 1; meeting 2 replaced them by a fixed 3, 2, 1 scale based on the target (section 8, step 4). |
| Class CO attainment is the share of students above target | It is the average of the student CO percentages. |
| 12 POs and 3 PSOs | Confirmed: PO1 to PO12 and PSO1 to PSO3. |
| Source file layouts are unknown | The workbook gives the layout; the templates in section 7 follow it. |
| Tool weights per CO come from instruction hours | Corrected: the syllabus fixes the marks each tool carries per CO (teachers cannot change them), and the LCA is split by the number of lab assignments per CO. Hours drive only the CO-PO mapping strength. |
| The CO-PO mapping is binary | Corrected: the ticks are a starting point; the mapping used has strengths 0 to 3 (Table 7). |
| PO attainment is the average of mapped CO attainment | Corrected: actual PO = PO target × overall CO attainment ÷ 3. |
| The end-term follows the unit-hours weighting | Corrected: the end-term is converted to 100 and counts equally for every CO. |

**Open items**

| ID | Question | Evidence in the workbook | Working answer used |
| --- | --- | --- | --- |
| O1 | What do Tables C and D contain? | Described as coordinator consolidations of direct and indirect results; no layout given | Not built in phase 1; generated later as views over the results |
| O2 | Which CO levels feed Table B and the overall CO attainment? | Table B shows direct levels 3, 3, 3, 2, 3 and overall 2.84. With the target-based rule of meeting 2 (O13), the typed Average row gives 3, 1, 2, 1, 1 and the formula-based averages give 2, 3, 3, 3, 3 | Apply the level rule of step 4 (O13) to the direct percentage; faculty to confirm, as this changes every PO actual value |
| O3 | Which hours-to-strength rule is right? | Table 5 gives 2, 2, 3, 1, 1 for the five COs; Table 4 shows 3, 3, 3, 2, 2 | Table 5 for the baseline; the teachers' final mapping overrides it. Meeting 2 confirmed that the rule is fixed and hardcoded |
| O4 | Which CO-PO source is authoritative? | Tables 1, 2 and 6 disagree (CO1 and PO3 is ticked in Table 1 but 0 in Tables 2 and 6); Table F lists CO5 and PO4 as 2 where Table 7 has 0 | Only the final mapping (Table 7) is used |
| O5 | How many hours does each lab assignment have? | Table 3 has no hours column; practical hours in Table 4 (6, 8, 16 for CO1 to CO3) imply 3, 3, 4, 4, 4, 4, 4, 4 | Add lab\_hours to template 4 |
| O6 | What identifies a student? | The workbook has a serial number and a name only; 291 students and 10 serial numbers missing between 1 and 301 | Roll number or PRN taken from the admission list |
| O7 | How are absent students marked? | No marker; zero marks appear | Scored 0; flagged when a marker is supplied |
| O8 | Do other courses use other tools, no lab or no end-term? | Sample has assignment, PBL, mid-term and LCA; MCQ and attendance columns exist but are 0. The notes say both 52 and 62 courses | Tools are data per course; one more course workbook of a different type needed to confirm |
| O9 | How is student-level PO attainment over four years defined? | The workbook is class-level per course; the meeting asked for one row per student over four years | Step 7 per student with the student's own CO levels, averaged over courses where the target is non-zero |
| O10 | Is the survey part of phase 1? | The workbook applies 80/20 with one survey percentage per CO; the earlier decision was direct only | Direct only; adding the survey percentage per CO is a small input and is recommended. Meeting 2: the faculty will explain the indirect part in a later session, and nothing is built for it until then |
| O11 | How are multi-CO units and assignments handled? | Tables 2 and 3 allow several COs per unit or assignment without a split rule | Split equally |
| O12 | Which is right for CO2 and CO4: the stated tool weights or the values in the sheet? | Tab 2 weights add up to 100 for every CO, but the CO2 and CO4 student values in Steps 2 and 3 use smaller effective weights (270 of 291 and 290 of 291 students differ from the formula by more than 0.1); CO1, CO3 and CO5 match for all students | The stated weights (Tab 2) are used; meeting 2 confirmed the method (marks times weight, 0 where a tool does not contribute) but did not look at the CO2 and CO4 values; the faculty confirm which version is intended |
| O13 | How exactly are the levels 3, 2 and 1 derived from the CO target? | Meeting 2: level 3 when the value exceeds the target, level 2 for 50 to 59, level 1 below 50, with 3, 2, 1 hardcoded. This fits a target of 60 but not the targets of 50 and 55 in the sample | Level 3 at or above the target, 2 from 50 up to the target, 1 below 50, no level 0; the floor of 50 is held in the rules file. Changes every level in Tables B and E and every PO actual value |
| O14 | Is the end-term really equal for all COs? | Meeting 2: the faculty described end-term questions of 5 marks for CO1, 5 for CO2 and 30 for CO3 to CO5, then took the full 40 marks for every CO. The workbook applies it equally | Equal for all COs, as in the workbook |

**Inconsistencies in the sample workbook.** The system computes these values and does not copy them.

- The Tab 1 row Actual attainment shows #REF! in every column.
- The target rows are typed by hand and differ: PO9 is 2.5 in Tab 1 and 2.6 in Table F, and PSO1 is 2.71 where the strengths give 2.6.
- The CO5 header says 67% internal and 33% end-term, but the numbers use 60/40.
- Tool names and maximums differ between tabs: assignment is out of 10 in one place and 5 in another, and Active Learning in Tab 2 is PBL in Tab 3. Meeting 2 settled this as a caption error: assignment is out of 5 and Active Learning (PBL) is out of 10.
- In step 2 the PBL marks are copied into the CO1 and CO2 columns although PBL carries no marks for those COs. The faculty called the calculation correct but the copy meaningless, so the step is dropped and the contribution is 0.
- The Average row in Step 3 is typed (60.85, 48.54, 52.43, 40.47, 47.45) and matches none of the sheet's own columns; the student rows carry 10 gaps in the serial numbers (291 students for serials 1 to 301).

**Assumptions taken from the faculty answers**

- Version 1 is direct attainment only; the 80/20 formula is built in with indirect weight 0.
- The calculation uses the final CO-PO mapping (Table 7), entered by the course teachers and coordinator.
- Python and PostgreSQL are the stack; the faculty want a report, not a user interface.
- Teachers have full rights; there is no admin role.
- Tool marks per CO, the level scale and the hours-to-strength rule are fixed; CO targets and Table 3 are inputs (meeting 2).

**Risks**

| Risk | Mitigation |
| --- | --- |
| Output differs from the workbook because it contains typed values or broken references | Reproduce the sample course in phase 1b and explain every difference with the faculty |
| Source files change layout between semesters | Strict templates with row-level validation; keep upload logs |
| Full rights for every teacher allows accidental changes | Audit log, configuration snapshot per run, ability to re-run from stored data |
| Rubrics or tools change in a later year | Rubric versions per course, so old batches keep their old weights |
| Poor data quality in marks lists | Reject bad rows, report errors, never load partial files |
| Only one course workbook is available to design against | Collect a second course of a different type (no lab or different tools) before phase 1a ends |

## 14. Build plan for Claude Code

Claude Code builds the MVP in 12 ordered steps, and each step ends with a check that must pass before the next one starts. The calculation core comes first and is validated against the sample course before any database or API exists, so that the formulas are settled while they are still cheap to change.

**Ground rules (put these in CLAUDE.md)**

- Read this document first. Section 8 (formulas), section 7 (what is hardcoded) and section 13 (open items) are the specification; export it to Markdown and commit it as docs/PROJECT.md.
- Do not invent rules. Where an open item applies, use its working answer and mark the line with a comment such as `# OPEN: O2`.
- The calculation core is made of pure functions: no database, no file access, no global state. It keeps full precision; rounding happens only in reports.
- Every hardcoded value lives in a YAML file validated at start-up, never in the calculation code.
- Loads are idempotent and run in a transaction. Every run stores a snapshot of the configuration it used.
- Student names and identifiers never go into logs, and the sample workbook with real names stays out of git (.gitignore it).
- Work one step at a time, commit after each step, and show the test results before moving on.

**Repository layout**

```text
obe-attainment/
  CLAUDE.md  README.md  pyproject.toml  docker-compose.yml  .env.example
  docs/PROJECT.md                 # this document exported to Markdown
  config/
    rules.yaml                    # global rules, thresholds, weights
    program_outcomes.yaml         # PO1 to PO12, PSO1 to PSO3
    courses/CET3011B.yaml         # course set-up for the sample course
  data/sample/                    # original workbook and extracted marks file (not in git)
  src/obe/
    config.py                     # pydantic models and loaders
    core/                         # weights.py, attainment.py, mapping.py, po.py (pure)
    ingest/                       # marks reader and validation
    db/                           # models.py, session.py, migrations/
    pipeline.py                   # validate, load, calculate, store
    reports/                      # excel.py, faculty.py
    api/                          # FastAPI app and login
    cli.py
  tests/  unit/  integration/  golden/
```

**Steps**

| # | Step | What to build | Done when |
| --- | --- | --- | --- |
| 1 | Project setup | Python project with ruff and pytest, docker-compose with PostgreSQL, .env.example, CLAUDE.md with the ground rules | pytest runs and the database container is reachable |
| 2 | Configuration layer | pydantic models and loaders for rules.yaml, program\_outcomes.yaml and the course YAML; write the YAML for CET3011B from section 7 and the workbook tables; checks: tool weights add up to 100 per CO, mapping values 0 to 3, theory hours 45 and lab hours 30, every CO has a target, level scale 3, 2, 1 and floor 50 come from rules.yaml | Bad configs fail with a clear message; one test per check |
| 3 | Core: steps 1 to 3 | Tool weight per CO including the LCA split by assignment count (marks-per-CO table kept as an intermediate, not exposed), student internal score in one calculation, CO attainment as 60% internal plus 40% end-term (end-term ×2.5) | Worked example holds: student 1 gets CO1 internal 43.43 and attainment 48.06, CO3 internal 37.5 and attainment 44.5; PBL contributes 0 to CO1 and CO2 |
| 4 | Core: steps 4 and 5 | Class average, CO level from the target-based rule (3, 2, 1 with floor 50), status against target, 80/20 total with indirect weight 0, overall CO attainment (Table E) | Boundary tests pass: target 60 gives level 2 at 59.99 and level 3 at 60, 49.99 gives level 1 and 50 gives level 2; target 50 gives level 3 at 50. With indirect weight 0 the total equals the direct value |
| 5 | Core: steps 6 and 7 | Hours per CO and baseline strength, PO and PSO target, actual and gap; per-student PO attainment behind a flag (open item O9) | PO1 target 3 and PO8 target 2.6 from Table 7; actual follows target × overall ÷ 3 |
| 6 | Marks ingest | Reader for the marks file (student id, name, assignment, PBL, mid-term, LCA, end-term); validation with a row-level error report; one-off script that extracts the marks file from the sample workbook | 291 rows load; bad files (marks above maximum, blanks, duplicates, unknown columns) give row-level errors and load nothing |
| 7 | Golden test on the sample | Recompute the whole sample course from the marks file and compare with the workbook; write discrepancy\_report.md | Student CO1, CO3 and CO5 match the workbook within 0.1 for all 291 students; CO2, CO4, typed averages and levels are listed in the report as open items O2 and O12 |
| 8 | Database | SQLAlchemy models and an Alembic migration for the 31 tables of section 9 (co\_survey and rubric\_version stay unused); idempotent seed loader that reads the YAML files | Migration runs on an empty database; seeding twice gives the same rows; unique and foreign-key constraints are tested |
| 9 | Pipeline and CLI | `obe seed` and `obe run --course CET3011B --marks <file>`: validate, load marks (replacing earlier marks for that course), calculate, store results with the configuration snapshot, write upload and audit logs | End-to-end run on the sample gives 291 × 5 student CO rows; a second run leaves no duplicates; database results equal the pure core output |
| 10 | Reports | Master Excel with the sheets of section 11 (openpyxl), Excel formulas for class averages, Table B and Table F, empty reason and action-plan columns for teachers; faculty report per course | Workbook formulas recalculated in LibreOffice give the same values as Python; the sheet list matches section 11 and the Tool weights sheet shows percentages only |
| 11 | API and login | FastAPI with password login (argon2 hashes, token sessions, seeded teachers), upload marks, run, download report, save gap actions; audit log on every write | Every route rejects unauthenticated calls; upload, run and download work end to end in a test |
| 12 | Hardening and handover | README (setup, run, how to add a course by writing a YAML file), Dockerfile, CI with ruff and pytest, open-items list updated with the faculty's answers | A fresh clone is running in three commands |

**Stop and ask the faculty when**

- The golden test shows differences beyond those in the discrepancy report.
- An open item changes a number in Table B or Table F (O2, O3, O4, O12, O13), because every PO actual value depends on it.
- A second course workbook arrives with other tools, no lab or no end-term (O8); extend the YAML shape, not the code.

**First prompt for Claude Code**

```text
Read docs/PROJECT.md. Build the MVP in the 12 steps of section 14, one step at a time.
Start with step 1 and step 2. Follow the ground rules, use the working answers for the
open items, and stop after each step to show the test results and wait for my go-ahead.
```

## 15. Changes from faculty meeting 2

Revision 2 (Oct 3, 2026) applies the second faculty meeting (transcript and rough minutes) to this document. The meeting covered Tab 1 to Tab 3 up to the direct CO attainment in Table B. The indirect part and the PO side (Tables E and F) were left for later sessions.

| # | Decision in meeting 2 | Earlier version | Sections changed |
| --- | --- | --- | --- |
| 1 | Tables 1 and 2 are given, Table 3 is the initial input, Table 4 is generated from them. The hours-to-strength rule is fixed and hardcoded | Rule hardcoded in the MVP but expected to become per-course | 4, 7, 8 (step 6), 13 (O3) |
| 2 | Tool marks per CO for the CCA tools are fixed by the syllabus and nobody can change them | Teacher input (template 7); teachers could add or change tools later | 2, 3, 5 (FR-04), 7, 8 (step 1), 9, 13 |
| 3 | LCA split is generated from Table 3: 1/N per assignment, added up per CO, times 30 | Same formula, described as a teacher-side count | 5 (FR-08), 8 (step 1) |
| 4 | The table of marks per tool and CO is intermediate and not shown; the percentage weights are the output | Marks and weights both shown | 4, 8, 9, 11 |
| 5 | Copying marks per CO and weighting them is one calculation; a tool with no marks for a CO contributes 0 | Two workbook steps; PBL marks copied into CO1 and CO2 | 4, 5 (FR-09), 8 (step 2), 13, 14 |
| 6 | Internal marks are converted to 60%, the end-term (40 marks) is taken as 40% | Same result, now explained | 8 (step 3) |
| 7 | CO targets are a user input, one per CO from each teacher, before the course starts | Entered by the coordinator from Form 8 and hardcoded in the MVP | 1, 3, 4, 7 |
| 8 | Level scale 3, 2, 1 is hardcoded and the level depends on the CO target | Fixed thresholds 60/50/40 set per course by the coordinator, with a level 0 | 1, 4, 5, 6, 8 (step 4), 9, 11, 13 (O2, O11, O13), 14 |
| 9 | In phase 1 Table B shows direct attainment % and Attained or Not attained (with the level) | Direct, indirect and total columns | 4, 8 (step 4), 11 |
| 10 | Caption errors in the workbook: assignment is out of 5 and Active Learning (PBL) is out of 10 | Listed as an unresolved inconsistency | 13 |
| 11 | The faculty will prepare a two-dimensional input table | Not planned | 12 |

**Effect on the sample numbers.** With the new level rule the formula-based CO levels are 2, 3, 3, 3, 3 (earlier 2 for every CO), the overall CO attainment is 2.8 (earlier 2), PO1 actual becomes 2.8 and PO8 actual 2.43.

**To confirm with the faculty.** The exact level bands (O13), the end-term split by CO (O14), and the indirect attainment and PO side, which are still to be explained.
