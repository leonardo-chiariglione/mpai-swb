# ACR - Developer Guidelines (Software Architecture)

**ACR** (Access Control Registration) enrols a new user by capturing their
**face and voice** and storing the resulting descriptors in the Shared-Storage
gallery that **MAC** later reads. This document is for software developers.

## 1. MPAI-AIF in brief
(Same platform as all HCI apps.)
- **AIM** - typed processing unit; **only data types matter at a port**.
- **Module (AIW)** - a composite AIM defined by an **L3** JSON (`AIMs/AMDs/`):
  sub-AIMs, boundary ports, topology.
- **Controller** - builds the Module from its L3 (via a *provider*), wires and
  runs it; exposes `MODULE_Start/RunAsync/ResumeAsync/Stop`.
- **User Agent (UA)** - acquires/delivers real-world data and **orchestrates**
  the Controller; described by a **WDL** `.orch` guidebook.
- **Shared Storage** - the enrolment **gallery**.

## 2. The ACR Module - `MMC-ACR-V2.5`
L3: `AIMs/AMDs/1MMC-ACR-V2.5-I01.json`. Sub-AIMs (provider leaves):

| Sub-AIM | Role | Engine |
|---|---|---|
| `PAF-EFD-V1.6` | Entity Face **Description** (enrol) | SCRFD + ArcFace -> Face Descriptors |
| `MMC-ESD-V2.5` | Entity Speech **Description** (enrol) | ECAPA-TDNN -> Speech Descriptors |
| `PAF-RSR-V1.6` (+ `PAF-PSD`, `MMC-TTS`, `PAF-GFD`) | Response & Scene Rendering | drives the avatar prompts |

**Boundary in:** `FaceObject`/`FaceTime`, `SpeechObject`/`SpeechTime`,
`PersonalStatus`, `Response`. **Boundary out:** `FaceDescriptors` (PAF-FDO),
`SpeechDescriptors` (MMC-SDO), `VocalResponse`, `MachineFaceDescriptors`.

The user's **name is a UA-level datum** (typed by the user), used as the gallery
key - it is not a Module port. ACR **writes** the enrolment into Shared-Storage
scope `"MMC-MAC-V2.5"` (the same scope MAC reads).

## 3. The User Agent
`MPAIApps/HCIApps/AcrApp/src/` - provider `AcrProvider.cs`, UA
`MainWindow.xaml.cs`, realising `UAs/Orchestration/HCI-ACR.orch`.

Flow: `MODULE_Start("MMC-ACR-V2.5")` -> speak *"Welcome to the CAV Access Control
Registration Service. Please type your name."* -> user **types a name** -> speak
*"Look at the camera."* -> capture face -> `RunAsync` -> suspend -> speak *"Please
speak a short sentence so I can learn your voice."* -> capture speech ->
`ResumeAsync` -> read the descriptors -> **write the gallery entry**
`subject:<name>` (face + voice embeddings, with capture times) -> present a
closing confirmation -> `Stop`.

Face capture is tagged `VisualObjectType = "Face"`; visual acquisition uses
**native Windows Media Capture** (no OpenCV).

## 4. Files this app needs (build closure)
- **App:** `MPAIApps/HCIApps/AcrApp/*`
- **AIF:** `AIF/V3.0/src/{Controller, Store, SharedStorage, GlobalStorage}`
- **UA library / MW:** `UAs/Lib/UaKit`, `MW/HciApi`
- **AIMs:** `AIMs/Core`; leaves `PAF/V1.6/EFD`, `MMC/V2.5/ESD`, `PAF/V1.6/PSD`,
  `MMC/V2.5/TTS`, `PAF/V1.6/GFD`; devices `CAE3/V1.0/AOA(.Windows)`,
  `MMC/V2.5/SOD(.Windows)`, `CVE/V1.0/VOA.Windows`
- **L3s:** `1MMC-ACR-V2.5-I01.json` + sub-AIM AMDs
- **Orchestration:** `UAs/Orchestration/HCI-ACR.orch`
- **Schemas:** the JSON schemas reachable from ACR's data types
- **Settings:** `AIMs/aim-settings.json` (TTS voice, SOA duration, EFD/ESD models)
- **Models (fetched separately):** SCRFD, ArcFace `glintr100.onnx`, ECAPA
  `ecapa-tdnn.onnx`, Piper voice `en_US-amy-medium`.

## 5. Build & run
```
D:\BI\MPAIApps\HCIApps\AcrApp\AcrAppBuild.bat
D:\BI\MPAIApps\HCIApps\AcrApp\AcrApp.exe
```
