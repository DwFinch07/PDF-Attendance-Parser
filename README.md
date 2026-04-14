PDF Attendance Parser
A desktop app that reads monthly attendance sign-in/sign-out PDFs from De Colores Learning Center & Childcare and generates an absence report — showing which days each child missed, and grouping children who share the same absent days.

## Features

- Auto-detects month and year from the PDF header
- Extracts attended days for each child using sign-in time patterns
- Groups children who missed the same days
- Prioritises consecutive absences when a child has more than 5 absent days
- Excludes holidays/closed days you specify — they're invisible to the report
- Saves the report as a plain `.txt` file
- Progress bar and status log keep you informed while parsing

## Screenshots

<img width="993" height="690" alt="image" src="https://github.com/user-attachments/assets/e5569f6c-c1c1-4139-898f-42c0f036c208" />



<img width="989" height="674" alt="image" src="https://github.com/user-attachments/assets/f0e1e6e8-61ba-46af-9cf0-7d8a6fb977f7" />

<img width="996" height="698" alt="image" src="https://github.com/user-attachments/assets/6c480358-884a-49b0-9e90-ec6f676e5872" />


Example of template used for this application: 
<img width="1107" height="583" alt="image" src="https://github.com/user-attachments/assets/5ffc4dc0-d026-45c4-8c23-b54f450154f1" />




## Requirements

Python 3.8+
The following packages (auto-installed on first run if missing):

customtkinter
pdfplumber



## Warning
This PDF scanner is purpose-built for De Colores Learning Center & Childcare (Arizona Department of Economic Security Sign-In / Sign-Out Record). While core scanning functions should work out of the box for most template layouts, the parsing logic: extract_child_name (if "" line) may require significant adjustments if the attendance sheet format differs from the expected template. Showcase of example template is above requirements.
