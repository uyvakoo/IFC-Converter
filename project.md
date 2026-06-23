AI-READY TECHNICAL SPECIFICATION - IFC SPATIAL CROPPING AND AR SUITE (PYTHON 3.11)

TARGET PLATFORM: Windows 10/11 (64-bit), air-gapped (no internet required after installation)
DISTRIBUTION: Single-folder .exe bundle via PyInstaller

1. SYSTEM OVERVIEW

Build a standalone Windows desktop application that batch-converts heavy IFC (BIM) files into two target formats:

Target 1: STP (STEP) - Purpose: Precise solid engineering geometry (CAD-grade)
Target 2: GLB (glTF + Draco) - Purpose: Highly compressed, low-poly visual assets for mobile AR (iPad/ARKit)

All processing is 100% local. No cloud services, no telemetry.

2. TECHNOLOGY STACK (EXACT VERSIONS)

Component: Python - Version: 3.11.x (64-bit) - Source: python.org
Component: Geometry/BIM - Version: ifcopenshell 0.8.0+ - Source: pip install ifcopenshell
Component: UI Framework - Version: PySide6 6.6.0+ - Source: pip install pyside6
Component: Distribution - Version: PyInstaller 6.5.0+ - Source: pip install pyinstaller
Component: Cryptography - Version: cryptography 42.0.0+ - Source: pip install cryptography
Component: Hardware ID - Version: machineid 0.3.0+ - Source: pip install machineid
Component: CLI Fallback - Version: IfcConvert.exe - Bundled in ./bin/ folder

CRITICAL WARNING: Use Python 3.11 exactly. Do not use 3.12 or later. IfcOpenShell wheels are not stable for newer versions.

3. CORE IP: DYNAMIC FILTERING AND CROPPING LOGIC

3.1 Dynamic Entity Filter (Color-Coded)
The UI must render a checklist of IFC entity classes. The user selects what to keep. The exported GLB must assign these exact placeholder colours for AR visibility:

IFC Class Group 1 (Structural): IfcWall, IfcSlab, IfcColumn, IfcBeam.
Assign Colour: Light Gray (0.8, 0.8, 0.8) which is Hex #CCCCCC.

IFC Class Group 2 (MEP): IfcPipeSegment, IfcDistributionFlowElement, IfcDuctSegment.
Assign Colour: Blue (0.2, 0.4, 0.8) which is Hex #3366CC.

IFC Class Group 3 (Architectural): IfcFurnishingElement, IfcDoor, IfcWindow, IfcSpace.
Assign Colour: Brown (0.6, 0.3, 0.1) which is Hex #994D1A.

IFC Class Group 4 (Cables): IfcCableSegment.
Assign Colour: Red (0.9, 0.2, 0.2) which is Hex #E63333.

Implementation Note for the Developer:
Use ifcopenshell.api.style.assign_item_style() to apply colours directly to representation items before serialisation. This overrides any existing material styles. The colour must be applied to the in-memory model before writing the temp file.

3.2 Storey-Based Cropping
Primary Method (Storey Dropdown):
Parse all IfcBuildingStorey entities from the IFC file.
Populate a dropdown menu with storey names (e.g. "Ground Floor", "Level 1").
When selected, compute the Z-axis bounds for that storey:
- Get all elements contained in that storey via IfcRelContainedInSpatialStructure.
- For each element, compute its bounding box using ifcopenshell.geom.create_shape() and read the .Bounds().
- Take the minimum Z and maximum Z across all elements. These are the crop limits.
- If no geometry exists, fallback to the storey's Elevation attribute plus and minus 3.0 meters.

Advanced Method (XYZ Box):
Provide manual X, Y, and Z min/max inputs (in meters) as an advanced toggle. When toggled on, this overrides the storey crop.

4. DATAFLOW AND EXECUTION ARCHITECTURE

4.1 Progress Streaming (Prevent RAM Explosion)
Use ifcopenshell.geom.iterator with lazy loading. Geometry must be processed element-by-element, never loading the entire model into RAM.

Inside the worker thread, the developer must filter elements based on the user's checklist:
- Read the selected classes from the UI (e.g., ['IfcWall', 'IfcSlab']).
- Inside the while loop, get the element using shape.geometry.ifc_element.
- If element.is_a() is not in the selected classes list, use "continue" to skip it.
- Only proceed with applying colours to elements that pass the filter.

Progress updates are emitted via the iterator's progress attribute, which is polled in the worker thread.

4.2 Sequential Batch Queue
Files must be processed one at a time. Do NOT attempt parallel IFC parsing as it causes memory corruption.
The UI must show: Queue position, current file name, and percentage complete.
The worker thread (QThread) must emit a progress_signal(int) to update the main UI.

4.3 Fallback Mechanism and Temporary File Pipeline (CRITICAL)
The Python API is used only for filtering and coloring. The final GLB and STP conversion must be delegated to the bundled IfcConvert.exe CLI.

Step-by-step pipeline for processing ONE file:
Step 1: Load the IFC using ifcopenshell.open(filename).
Step 2: Filter Elements based on the Storey or XYZ crop rules defined in section 3.2.
Step 3: Apply the Colors (Section 3.1) to the filtered in-memory elements.
Step 4: Write this filtered and colored model to a temporary file in the system temp folder. Use the exact code:
temp_path = os.path.join(tempfile.gettempdir(), "cropped_model.ifc")
model.write(temp_path)
Step 5: Execute the IfcConvert.exe CLI on this temp_path to generate the final STP or GLB.
Step 6: Delete the temporary .ifc file after successful conversion.

If the Python API raises any exception during steps 1 to 4, log the error to conversion_report.txt and abort that file. Do not proceed to the CLI.

5. AR TRANSFORMATION AND ENTERPRISE OUTPUT

5.1 GLB Real-World Scale and Coordinates
Unit conversion must read the project units using:
import ifcopenshell.util.unit
scale, unit_type = ifcopenshell.util.unit.calculate_unit_scale(model)

Apply the following actions based on the project unit:
- If MILLIMETER: Divide all vertex coordinates by 1000.0.
- If FEET: Multiply by 0.3048.
- If Other or missing: Fallback to meters (scale = 1.0).

Coordinate Transform (Z-up to Y-up) to match Apple ARKit:
For GLB export, the Python API is used only for cropping and coloring. The final GLB conversion MUST fall back to the bundled IfcConvert.exe CLI with the --y-up flag.
The Python script writes the cropped IFC to the temp file, then executes:
IfcConvert --y-up --draco --optimize --use-material-names temp.ifc output.glb
(Note: --use-material-names is mandatory to preserve the colours applied in Python).

For STP Export (clean geometry without colours):
The Python script executes:
IfcConvert --convert-back-units temp.ifc output.stp

5.2 Detailed Debug Log
Generate a file named conversion_report.txt in the output folder containing:
- Timestamp
- Input filename
- Cropping coordinates or storey name used
- Active filter list (which entity classes were kept)
- Number of entities processed
- Final file sizes in bytes
- Elapsed time in seconds

6. AIR-GAPPED SECURITY AND LICENSING (STRONG KEYS)

6.1 Machine Hash
On first startup, generate a unique machine ID using the machineid library. This queries the Windows UUID and motherboard serials without admin privileges.
Use the code: import machineid; machine_hash = machineid.id()
Display this hash in a copyable text box in the License Activation window.

6.2 RSA License Validation
The public key must be hard-coded inside the .exe (PEM format, 4096-bit RSA).
The private key is kept only by the vendor (you).
The license file (license.key) is a JSON containing:
{
  "machine_hash": "<hash>",
  "expiry": "2026-12-31",
  "signature": "<base64_rsa_signature>"
}

Validation steps:
1. Read license.key from the user-selected path.
2. Verify the RSA signature using the hard-coded public key and cryptography.hazmat.primitives.asymmetric.padding.PKCS1v15().
3. Check that the machine_hash matches the current machine.
4. Check that the expiry date has not passed.
5. If all pass, unlock the main UI. Otherwise show: "Invalid license - contact vendor."

System Time Rollback Protection:
The software must prevent users from changing the system clock to bypass expiry.
- On first successful activation, store the current validation timestamp in the Windows Registry.
- On every subsequent startup, check if the current system time is earlier than the previously stored Registry timestamp.
- If the system time is earlier than the stored timestamp, show: "System clock tampered - license revoked" and lock the UI immediately.
- To handle air-gapped environments, optionally attempt to fetch UTC time from an NTP server (pool.ntp.org). If the NTP fails, rely on the Registry check. The ntplib library must be added to requirements.txt.

6.3 Anti-Debug and Obfuscation
- Use PyInstaller's --key option to encrypt the bytecode.
- Strip all debug symbols using --strip and --noupx (UPX can trigger false positives in antivirus).
- Do not include any print() statements that reveal logic or stack traces to the user.
- Use obfuscation (e.g. pyarmor or pyminifier) on the licensing and hashing modules specifically. This is strongly recommended.

7. UI SPECIFICATION - LIGHT MODE PROFESSIONAL

7.1 Colour Palette
Main accent: #3455FA (blue)
Background: #FFFFFF (white)
Text: #000000 (black)
Secondary text: #555555
Borders and dividers: #E0E0E0
Success / progress bar: #34A853
Error messages: #EA4335

The developer must use the Qt-Material stylesheet library with a light theme and set invert_secondary=True.

7.2 Layout (Two Windows)

Window 1 - License Activation (modal):
Title: "License Activation"
Content:
- A label saying "Machine Hash:" followed by a copyable text box containing the generated hash.
- Instruction text: "Email this hash to your vendor to receive a license key."
- A "Browse" button to load the license.key file from disk.
- An "Activate" button that validates the license. On success, it closes the window. On failure, it shows an error dialog.

Window 2 - Main Application:
Top bar: Contains the App title and version number.
Left panel (settings):
- Entity checklist with checkboxes for each IFC class group (Structural, MEP, Architectural, Cables).
- Storey dropdown (populated from the loaded IFC).
- An "Advanced" toggle labelled "Manual XYZ Crop" which reveals X, Y, and Z min/max input fields.
Centre panel (batch queue):
- An "Add Files" button to select multiple IFC files.
- A list view showing the selected files with status columns (Pending, Processing, Done, Error).
- A global progress bar at the bottom of this panel.
Bottom bar:
- A "Start Conversion" button.
- An "Output Folder" selector (browse dialog).
- An "Open Report" button that opens conversion_report.txt in the default text editor.

8. DEVELOPER DELIVERABLES AND COMPILATION PROTOCOL

Payment is contingent upon delivering ALL of the following:

8.1 Source Code
- Complete, clean Python source code with docstrings for every function.
- A requirements.txt file with exact versions for all dependencies.
- A hooks/ folder containing the necessary PyInstaller hooks (see section 8.3).

8.2 Bundled IfcConvert.exe
- The developer must download IfcConvert.exe from the official IfcOpenShell release page (version 0.8.0).
- Place it inside the project as ./bin/ifcconvert.exe.
- This file must be included inside the final PyInstaller bundle.
- Reference this file in the code using sys._MEIPASS to get the correct runtime path.

8.3 PyInstaller Build Command (One-Folder Bundle)
The developer must use this exact command structure:

pyinstaller --onedir --name "IFC_Converter" --add-data "bin/ifcconvert.exe;bin/" --hidden-import=ifcopenshell.express.express_parser --hidden-import=ifcopenshell.util.unit --hidden-import=ifcopenshell.geom.serializers --key "your-encryption-key-here" --strip --noupx main.spec

CRITICAL NOTE: The hidden import for ifcopenshell.express.express_parser is mandatory. Without it, PyInstaller will fail with the error: [Errno 2] No such file or directory: express_parser.py.

8.4 Testing Protocol
The developer must test the PyInstaller build on a clean Windows Virtual Machine with no Python installed. They must confirm that the .exe executes successfully and all features work. They must provide a signed test report with screenshots.

8.5 Build Guide
The developer must provide a detailed, step-by-step Windows build guide including:
- The exact Python version (3.11.x) and the download link.
- How to set up the virtual environment (venv).
- The exact command: pip install -r requirements.txt.
- The PyInstaller command and any customisations made to the .spec file.
- Optional: Instructions on how to sign the final .exe with a code-signing certificate.

9. ERROR HANDLING - MUST COVER THESE SCENARIOS

Scenario 1: IFC file is corrupt or unreadable.
Action: Log the error to conversion_report.txt, skip this file, and continue processing the next file in the queue.

Scenario 2: Output folder has no write permissions.
Action: Show an error dialog immediately, ask the user to pick another folder, and do not start conversion until a valid folder is selected.

Scenario 3: IfcConvert.exe is not found in the bundle.
Action: Log a fatal error, show a message box to the user, and abort the entire conversion process.

Scenario 4: Conversion takes longer than 1 hour.
Action: Keep the UI fully responsive. The progress bar must update every 2 seconds at a minimum to show the application is still alive.

Scenario 5: User closes the application during conversion.
Action: Show a confirmation dialog asking if they want to cancel. If confirmed, terminate the worker thread gracefully and close the app. Do not corrupt the temp files.

10. FINAL NOTES FOR THE DEVELOPER

- Do NOT use ifcopenshell.file(filename) with apply=True. This loads everything into RAM and will crash on large files. Always use the iterator as described in section 4.1.
- STP export is done exclusively via the IfcConvert CLI fallback. The Python API does not have native STP serialisation.
- GLB export relies on the IfcConvert CLI for proper Y-up AR transformation. Do not try to rotate the shapes manually in Python.
- All cryptographic operations must use the cryptography library (specifically the hazmat module). Do not use pycryptodome, as it has GPL licensing contamination.
- The developer must ensure the temp folder is cleaned up after each conversion to prevent the hard drive from filling up.

---

