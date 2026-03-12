# ⭐ Connected Little Box – Installation Guide  
### Using Visual Studio Code + Raspberry Pi Pico Extension

This guide shows you how to:

1. Install Visual Studio Code and the Raspberry Pi Pico extension  
2. Flash MicroPython onto your Raspberry Pi Pico  
3. Download the Connected Little Box (CLB) repository  
4. Upload the entire project with one right-click  
5. Run and verify the system  

---

## 🛠️ 1. Install Visual Studio Code and the Pico Extension

### 1. Install VS Code  
Download from:  
**https://code.visualstudio.com**

### 2. Install the Raspberry Pi Pico Extension  
Inside VS Code:

1. Open **Extensions**  
2. Search for:  
   ```
   Raspberry Pi Pico
   ```
3. Install:  
   **“Raspberry Pi Pico – RP2040 Tools”**

This extension provides:

- MicroPython flashing  
- REPL terminal  
- File explorer  
- **One-click Upload Project to Pico**  

---

## 🔌 2. Connect the Pico in BOOTSEL Mode

To install firmware:

1. Disconnect the Pico  
2. Hold the **BOOTSEL** button  
3. Plug in the USB cable  
4. Release BOOTSEL  
5. A drive named **RPI-RP2** will appear  

---

## 🐍 3. Install MicroPython Firmware

Inside VS Code:

1. Press **Ctrl+Shift+P**  
2. Run:

   ```
   Raspberry Pi Pico: Install MicroPython
   ```

3. Select your board type (Pico / Pico W / Pico 2 / Pico 2 W)

The `.uf2` is flashed automatically and the Pico reboots.

✔ MicroPython is now installed.

---

## 📦 4. Obtain the Connected Little Box Repository

Clone the repo using Git:

```bash
git clone https://github.com/CrazyRobMiles/MicroPython-Connected-Little-Box
cd MicroPython-Connected-Little-Box
```

Or use:

- VS Code → **Source Control** → **Clone Repository** → paste the URL

The MicroPython project is in the **firmware** folder in the repo. To activate the Raspberry Pi PICO extension you need to open this folder using Visual Studio Code. The best way to do this is to use the Visual Studio Code **File** dialogue to open the folder. Make sure that your PICO is plugged in and running MicroPython before opening the folder. 

![Visual Studio Code editor with the Mpy FS element highlighted](/docs/guides/images/Visual%20Studio%20Code%20Mpy%20FS.png)

The figure above shows Visual Studio open and displaying the files held on the PC in the repo. You want to work on the files held on the PICO. Click the "Toggle Mpy FS" button indicated by the red arrow. 

![Visual Studio Code editor with the Mpy FS open](/docs/guides/images/Visual%20Studio%20Code%20Mpy%20Open.png)
The figure above shows that the MPY Remote Workspace is now visible in the Explorer window. At the moment there are no files in the explorer, because the device is empty. Now we need to upload files from the repo to the Pico. 


---

## 📤 5. Upload the CLB Project to the Pico  
### ⭐ The easiest method — **Right-click → Upload Project to PICO**

The Raspberry Pi Pico extension makes deployment extremely simple.

![Visual Studio Code editor with the properties dialog for a local file open](/docs/guides/images/Visual%20Studio%20Code%20Upload%20Project%20to%20PICO.png)

1. Open the **top-level CLB folder** in VS Code  
2. In the Explorer sidebar, **right-click a file in this folder**  In the screenshot above I've right-clicked settings.json
3. Select:

   ```
   Upload Project to PICO
   ```

The extension will:

- Upload all project files  
- Preserve the folder structure  
- Replace only modified files  
- Confirm transfer success  

This is the recommended installation method.

![Visual Studio Code showing local and PICO projects files in Explorer](/docs/guides/images/Visual%20Studio%20Code%20showing%20two%20projects.png)

Now you will see two copies of the project in the explorer. The upper project is on your machine. The lower project is on the PICO. **This is very confusing.** If you open files in the upper project you can edit and save them but they will have no effect on your program when you run it. If you open the files in the lower project you will be working on the files on the device. You will notice a short delay when you open a file as it is transferred from the PICO for you. If a MicroPython program is running in the device you will find that opening a file on the device will not succeed. The framework has a **stop** command you can use to stop it running and allow file transfers to take place.  

You can open the `settings.json` file and add WiFi settings and enable WiFi, along with MQTT and other managers. When you have finished your edits you can save the file back into the device. 

If you want to copy files from the PICO back into the repo on the PC you can right click on any file in the PICO filespace and select **Download project from PICO**



---

## ▶️ 6. Ensure CLB Starts Automatically (`main.py`)

You should have a `main.py` on the Pico that launches CLB:

```python
import clb

device = clb.CLB("/settings.json")
device.setup()

while device.running:
    device.update()
    device.update_console()
```

This script ensures the CLB framework starts on every boot. If you want to run the project inside Visual Studio Code you should open the **main.py** file in the editor (remember to open the PICO copy and not the Repo copy) and then select **Run** from the **bottom** menu. 

---

## 🧪 7. Verify Installation Using the REPL

To open the REPL:

- Use the VS Code sidebar → **Raspberry Pi Pico → Open REPL**

On startup you should see:

```
[CLB] Built unified interface with XX commands/services
```

Test a few commands:

```
help
blink.start
pixel.fill 50 0 0
```

If the LED blinks and pixels update, CLB is installed correctly.

---

## 🔧 Troubleshooting

### **Pico not detected**
- Try another USB cable (must support data)  
- Try another USB port  
- Ensure that another process has not connected to the device
- On Windows, install the Pico USB serial driver

### **CLB cannot find files**
Make sure that you are using the correct project in the explorer. 
### **Code changes have no effect**
Make sure that you are editing the files on the PICO. There can also be a problem if you copy a single file from the repo to the PICO. It might not be put in the correct subfolder on the PICO.  

---

## 🎉 You’re Ready to Build Connected Little Boxes!

You now have:

- A complete CLB installation  
- Firmware deployable via one-click  
- REPL access for debugging  
- A stable environment for running managers, animations, scripts, and more  
