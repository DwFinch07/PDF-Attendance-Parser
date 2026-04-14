PDF Attendance Parser
A desktop app that reads monthly attendance sign-in/sign-out PDFs from De Colores Learning Center & Childcare and generates an absence report — showing which days each child missed, and grouping children who share the same absent days.

Features

Auto-detects month and year from the PDF header.
Extracts attended days for each child using sign-in time patterns.
Groups children who missed the same days (for efficient notification).
Prioritises consecutive absences when a child has more than 5 absent days.
Excludes holidays/closed days you specify — they're invisible to the report.
Saves the report as a plain .txt file.
Progress bar and status log keep you informed while parsing.

Screenshots

<img width="993" height="690" alt="image" src="https://github.com/user-attachments/assets/e5569f6c-c1c1-4139-898f-42c0f036c208" />



<img width="989" height="674" alt="image" src="https://github.com/user-attachments/assets/f0e1e6e8-61ba-46af-9cf0-7d8a6fb977f7" />


<img width="998" height="679" alt="image" src="https://github.com/user-attachments/assets/8a239237-9178-49f5-aa36-352980699cb0" />

<img width="992" height="682" alt="image" src="https://github.com/user-attachments/assets/dddd0485-cf5f-46ad-a3c5-0e261c297773" />



Requirements

Python 3.8+
The following packages (auto-installed on first run if missing):

customtkinter
pdfplumber



Warning: This PDF scanner only works for De Colores Learning Center & Childcare, major changes will have to be done with parsing function (extract_child_name (if "" line), most functions should work out of the box depending on how attendance sheet is formatted) to scan a different template. Ex of how template looked for my application: <img width="1107" height="583" alt="image" src="https://github.com/user-attachments/assets/5ffc4dc0-d026-45c4-8c23-b54f450154f1" />
