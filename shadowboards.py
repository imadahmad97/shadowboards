import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog
from PIL import Image, ImageTk
import cv2
import numpy as np
import subprocess
import os
import re
import tempfile
from picamera2 import Picamera2
import RPi.GPIO as GPIO
import time
import webbrowser
import xml.etree.ElementTree as ET
import utils.barrel as barrel


# Initialize the camera
picam2 = Picamera2()

# Set the camera resolution to ensure consistent frame sizes
picam2.configure(picam2.create_still_configuration(main={"size": (640, 480)}))

# GPIO setup
GPIO.setmode(GPIO.BCM)

# Define the GPIO pin numbers where the buttons are connected
red_button_pin = 17
blue_button_pin = 27
green_button_pin = 22

# Set up the button pins as inputs with pull-up resistors
GPIO.setup(red_button_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(blue_button_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(green_button_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

# Global variables
running = True
image_count = 0
svg_files = []
output_directory = ""
run_title = ""
directory_dialog_open = False
gpio_monitor_task = None
PIXELS_PER_CM = 24.16

# Barrel Distortion Variables (calculated with barrel.py)
ret = barrel.ret
mtx = barrel.mtx
dist = barrel.dist
rvecs = barrel.rvecs
tvecs = barrel.tvecs

# Variables for crop zone selection
start_x = None
start_y = None
rect_id = None
crop_coords = None
crop_selected = False
rectangle_coords = None  # Store rectangle coordinates separately


# Function to switch to the main app screen
def go_to_app():
    home_frame.pack_forget()
    main_frame.pack(padx=0, pady=0)
    root.update_idletasks()  # Force GUI update

    # Schedule select_directory to run after a short delay
    root.after(100, select_directory)


# Function to allow the user to open the docs
def open_docs():
    webbrowser.open("https://docs.example.com")


# Function to capture image and convert to SVG
def capture_and_convert_to_svg():
    global image_count, output_directory, PIXELS_PER_CM

    if not output_directory:
        messagebox.showerror("Error", "Please select an output directory first.")
        return

    if not crop_selected:
        messagebox.showerror("Error", "Please finalize the crop zone first.")
        return

    # Ensure the output directory has folders for photos and SVGs
    photos_dir = os.path.join(output_directory, "photos")
    svgs_dir = os.path.join(output_directory, "svgs")
    os.makedirs(photos_dir, exist_ok=True)
    os.makedirs(svgs_dir, exist_ok=True)

    # Capture and process the image
    image_count += 1
    image_path = os.path.join(photos_dir, f"captured_image_{image_count}.jpg")
    svg_path = os.path.join(svgs_dir, f"output_image_{image_count}.svg")

    # Capture image from camera
    picam2.capture_file(image_path)

    # Load the captured image
    image = cv2.imread(image_path)

    h, w = image.shape[:2]
    newcameramtx, roi = cv2.getOptimalNewCameraMatrix(mtx, dist, (w, h), 1, (w, h))

    # undistort
    dst = cv2.undistort(image, mtx, dist, None, newcameramtx)

    # crop the image
    x, y, w, h = roi
    image = dst[y : y + h, x : x + w]

    # If crop zone is selected, crop the image
    if crop_selected and crop_coords:
        x0, y0, x1, y1 = map(int, crop_coords)
        # Ensure coordinates are within the image dimensions
        x0 = max(0, min(x0, image.shape[1]))
        x1 = max(0, min(x1, image.shape[1]))
        y0 = max(0, min(y0, image.shape[0]))
        y1 = max(0, min(y1, image.shape[0]))
        image = image[y0:y1, x0:x1]
        # Save the cropped image back to image_path
        cv2.imwrite(image_path, image)

    # Load the last captured image and display it on the label
    last_img = Image.open(image_path)
    last_img = last_img.resize((200, 200))
    last_imgtk = ImageTk.PhotoImage(last_img)

    lbl_last_photo.imgtk = last_imgtk  # Keep a reference to avoid garbage collection
    lbl_last_photo.configure(image=last_imgtk)

    # Convert the image to grayscale
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # Apply a binary threshold to separate the object from the background
    _, binary = cv2.threshold(gray, 128, 255, cv2.THRESH_BINARY_INV)

    # Find contours of the object
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # Create a mask for the object outline
    mask = np.zeros_like(gray)
    cv2.drawContours(mask, contours, -1, (255), thickness=2)

    # Invert the mask to have the outline as black on white
    mask_inv = cv2.bitwise_not(mask)

    # Save the mask to a temporary PGM file
    with tempfile.NamedTemporaryFile(suffix=".pgm", delete=True) as temp_pgm:
        cv2.imwrite(temp_pgm.name, mask_inv)

        # Run potrace using the temporary PGM file
        subprocess.run(["potrace", "-s", "-o", svg_path, temp_pgm.name])

    # Compute the width and height in pixels
    height_px, width_px = image.shape[:2]

    # Compute the width and height in centimeters
    pixels_per_cm = PIXELS_PER_CM  # Your calculated value
    width_cm = width_px / pixels_per_cm
    height_cm = height_px / pixels_per_cm

    # Modify the SVG file to include the correct dimensions
    import xml.etree.ElementTree as ET

    # Parse the SVG file
    tree = ET.parse(svg_path)
    root_svg = tree.getroot()

    # Define the SVG namespace
    svg_ns = {"svg": "http://www.w3.org/2000/svg"}

    # Remove existing width, height, and viewBox attributes
    for attr in ["width", "height", "viewBox"]:
        if attr in root_svg.attrib:
            del root_svg.attrib[attr]

    # Set new width, height, and viewBox attributes
    root_svg.set("width", f"{width_cm}cm")
    root_svg.set("height", f"{height_cm}cm")
    root_svg.set("viewBox", f"0 0 {width_px} {height_px}")
    print(width_cm)
    print(height_cm)

    # Write the modified SVG back to file
    tree.write(svg_path)

    # Add the SVG path to the list for combining later
    svg_files.append(svg_path)

    lbl_pics_taken.config(text=f"Photos Processed: {image_count}")


# Function to combine all SVGs into a single file
def combine_svgs():
    global svg_files, output_directory, PIXELS_PER_CM

    if not svg_files:
        messagebox.showerror("Error", "No SVG files to combine.")
        return

    combined_svg_path = os.path.join(output_directory, "combined_output.svg")

    individual_svgs = []

    # Pixels per cm
    pixels_per_cm = PIXELS_PER_CM  # Your calculated value

    # Variables to calculate total width and height in pixels
    max_width_px = 0
    total_height_px = 0

    from lxml import etree

    # Parse all SVGs to extract their width, height, and content
    for svg_file in svg_files:
        # Parse the SVG file using lxml
        parser = etree.XMLParser(ns_clean=True, recover=True)
        tree = etree.parse(svg_file, parser)
        root_svg = tree.getroot()

        # Extract width and height from the SVG root element
        width_cm = float(root_svg.get("width").replace("cm", ""))
        height_cm = float(root_svg.get("height").replace("cm", ""))

        # Corrected calculations: Multiply instead of divide
        width_px = width_cm * pixels_per_cm
        height_px = height_cm * pixels_per_cm

        # Update total dimensions
        max_width_px = max(max_width_px, width_px)
        total_height_px += height_px

        # Remove namespace prefixes for simplicity
        for elem in root_svg.iter():
            if not hasattr(elem.tag, "find"):
                continue  # It's a comment or similar
            i = elem.tag.find("}")
            if i >= 0:
                elem.tag = elem.tag[i + 1 :]

        # Extract the inner content of the SVG (excluding the outer <svg> tag)
        svg_inner = list(root_svg)

        individual_svgs.append(
            {"width_px": width_px, "height_px": height_px, "content": svg_inner}
        )

    # Compute total dimensions in cm
    max_width_cm = max_width_px / pixels_per_cm
    total_height_cm = total_height_px / pixels_per_cm

    # Create the combined SVG root element
    SVG_NS = "http://www.w3.org/2000/svg"
    NSMAP = {None: SVG_NS}

    combined_svg = etree.Element("svg", nsmap=NSMAP)
    combined_svg.set("version", "1.1")
    combined_svg.set("width", f"{max_width_cm}cm")
    combined_svg.set("height", f"{total_height_cm}cm")
    combined_svg.set("viewBox", f"0 0 {max_width_px} {total_height_px}")

    current_y = 0  # Starting Y position in pixels

    for svg_info in individual_svgs:
        # Create a group element with the appropriate translation
        g_element = etree.SubElement(combined_svg, "g")
        g_element.set("transform", f"translate(0, {current_y})")

        # Append the individual SVG content to the group
        for elem in svg_info["content"]:
            g_element.append(elem)

        # Update the Y position for the next SVG
        current_y += svg_info["height_px"]

    # Write the combined SVG to file
    tree = etree.ElementTree(combined_svg)
    tree.write(
        combined_svg_path, encoding="UTF-8", xml_declaration=True, pretty_print=True
    )

    messagebox.showinfo(
        "Success", f"All SVGs combined and saved as {combined_svg_path}"
    )

    # Reset for the next set
    global image_count
    image_count = 0
    svg_files = []
    lbl_pics_taken.config(text=f"Photos Processed: {image_count}")


# Function to select a directory
def select_directory():
    global output_directory, run_title, image_count, crop_selected, rect_id, crop_coords, rectangle_coords
    global start_x, start_y, end_x, end_y  # Declare as global

    directory_dialog_open = True
    directory = filedialog.askdirectory(title="Choose a folder to save your files")

    # Create a dialog with an Entry widget for folder name input
    folder_name_window = tk.Toplevel(root)
    folder_name_window.title("Folder Name")

    label = tk.Label(
        folder_name_window,
        text="What do you want to name the folder your files are stored in? (ex. Run 1)",
    )
    label.pack(pady=10)

    entry = tk.Entry(folder_name_window, width=30)
    entry.pack(pady=10)

    # Add a button to open the on-screen keyboard
    btn_keyboard = tk.Button(
        folder_name_window,
        text="Open Keyboard",
        command=lambda: on_screen_keyboard(entry),
    )
    btn_keyboard.pack(pady=10)

    def confirm_folder_name():
        global run_title
        run_title = entry.get()
        folder_name_window.destroy()

    # Add a confirm button to finalize the folder name
    confirm_button = tk.Button(
        folder_name_window, text="Confirm", command=confirm_folder_name
    )
    confirm_button.pack(pady=10)

    # Set focus to the folder name window and lock the window focus
    folder_name_window.grab_set()
    folder_name_window.focus_force()

    folder_name_window.wait_window()  # Wait for the dialog to close

    directory_dialog_open = False
    if directory and run_title:
        output_directory = os.path.join(directory, run_title)
        lbl_selected_dir.config(text=f"Output Directory: {output_directory}")

        # Ensure the photos and svgs directories exist
        photos_dir = os.path.join(output_directory, "photos")
        os.makedirs(photos_dir, exist_ok=True)

        # Check the existing files in the photos directory and reset image_count accordingly
        existing_images = [f for f in os.listdir(photos_dir) if f.endswith(".jpg")]
        image_count = len(
            existing_images
        )  # Set the image_count based on existing images

        # Update the label for Photos Processed after selecting the directory
        lbl_pics_taken.config(text=f"Photos Processed: {image_count}")

        # Create a default rectangle that fills the canvas
        start_x, start_y = 100, 100  # You can adjust these default values
        end_x, end_y = 540, 380
        crop_coords = (start_x, start_y, end_x, end_y)
        rectangle_coords = (start_x, start_y, end_x, end_y)

        # If there's an existing rectangle, delete it
        if rect_id:
            lbl_camera.delete(rect_id)
        rect_id = lbl_camera.create_rectangle(
            start_x, start_y, end_x, end_y, outline="red", width=2
        )
        lbl_camera.tag_raise(rect_id)  # Ensure rectangle is above the image

        root.update_idletasks()  # Update the GUI before showing the messagebox
        messagebox.showinfo(
            "Select Crop Zone",
            "Adjust the crop zone rectangle over the live camera feed. Press the green button or Enter to finalize.",
        )
    else:
        lbl_selected_dir.config(text="No Directory Selected")


def on_screen_keyboard(entry):
    keyboard_window = tk.Toplevel(root)
    keyboard_window.title("On-Screen Keyboard")

    buttons = [
        ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0"],
        ["q", "w", "e", "r", "t", "y", "u", "i", "o", "p"],
        ["a", "s", "d", "f", "g", "h", "j", "k", "l"],
        ["z", "x", "c", "v", "b", "n", "m", "Del"],
        ["Space", "Enter"],
    ]

    def key_press(key):
        if key == "Space":
            entry.insert(tk.END, " ")
        elif key == "Del":
            current_text = entry.get()
            entry.delete(0, tk.END)
            entry.insert(0, current_text[:-1])
        elif key == "Enter":
            keyboard_window.destroy()
        else:
            entry.insert(tk.END, key)

    for row in buttons:
        frame = tk.Frame(keyboard_window)
        frame.pack()
        for button in row:
            b = tk.Button(
                frame,
                text=button,
                width=5,
                height=2,
                command=lambda b=button: key_press(b),
            )
            b.pack(side=tk.LEFT)

    # Force the focus to the keyboard window and grab the focus
    keyboard_window.grab_set()
    keyboard_window.focus_force()


# Function to handle the crop button click
def handle_crop_button():
    global crop_selected, rect_id, crop_coords
    if crop_selected:
        # Allow user to change the crop zone again
        crop_selected = False
        # Remove any existing rectangle
        if rect_id:
            lbl_camera.delete(rect_id)
            rect_id = None
        crop_coords = None
        # Update the button text to "Confirm Crop Zone"
        btn_crop.config(text="Confirm Crop Zone")
        # Optionally, show a message
        messagebox.showinfo(
            "Change Crop Zone",
            "Adjust the crop zone rectangle over the live camera feed. Press the 'Confirm Crop Zone' button or Enter to finalize.",
        )
    else:
        # Crop is not selected, so confirm the crop zone
        finalize_crop_zone()
        # Button text will be updated in finalize_crop_zone()


# Function to finalize the crop zone
def finalize_crop_zone(event=None):
    global crop_selected, rect_id
    if crop_coords:
        crop_selected = True
        messagebox.showinfo("Crop Zone Finalized", "Crop zone has been finalized.")
        # Optionally, remove the rectangle since the live feed will now show only the cropped area.
        if rect_id:
            lbl_camera.delete(rect_id)
            rect_id = None
        # Update the button text to "Change Crop Zone"
        btn_crop.config(text="Change Crop Zone")


# Functions for crop zone selection
def start_crop(event):
    global start_x, start_y, rect_id
    if crop_selected:
        return  # Do not allow re-selection unless reset
    start_x = event.x
    start_y = event.y


def update_crop(event):
    global rect_id, rectangle_coords
    if crop_selected:
        return  # Do not allow re-selection unless reset
    end_x, end_y = event.x, event.y
    # Delete the previous rectangle if it exists
    if rect_id:
        lbl_camera.delete(rect_id)
    rect_id = lbl_camera.create_rectangle(start_x, start_y, end_x, end_y, outline="red")
    # Store rectangle coordinates
    rectangle_coords = (start_x, start_y, end_x, end_y)
    # Update crop_coords so the rectangle remains after releasing the mouse
    crop_coords = rectangle_coords


def finish_crop(event):
    global crop_coords
    if crop_selected:
        return  # Do not allow re-selection unless reset
    end_x, end_y = event.x, event.y
    x0 = min(start_x, end_x)
    y0 = min(start_y, end_y)
    x1 = max(start_x, end_x)
    y1 = max(start_y, end_y)
    crop_coords = (x0, y0, x1, y1)
    # Rectangle remains on the canvas


# Function to update the live camera feed in the GUI
def update_camera_feed():
    frame = picam2.capture_array()  # Capture a frame from the camera
    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)  # Convert the frame to RGB

    # If crop zone is selected, crop the frame
    if crop_selected and crop_coords:
        x0, y0, x1, y1 = map(int, crop_coords)
        # Ensure coordinates are within the frame dimensions
        x0 = max(0, min(x0, frame.shape[1]))
        x1 = max(0, min(x1, frame.shape[1]))
        y0 = max(0, min(y0, frame.shape[0]))
        y1 = max(0, min(y1, frame.shape[0]))
        frame = frame[y0:y1, x0:x1]
        # Resize the frame to fit the canvas
        frame = cv2.resize(frame, (640, 480), interpolation=cv2.INTER_AREA)
    else:
        # Resize the frame to fit the canvas
        frame = cv2.resize(frame, (640, 480), interpolation=cv2.INTER_AREA)

    img = Image.fromarray(frame)  # Convert frame to a PIL image
    imgtk = ImageTk.PhotoImage(image=img)  # Convert PIL image to ImageTk format

    # Remove the previous image
    lbl_camera.delete("live_image")

    # Display the image
    lbl_camera.imgtk = imgtk
    image_id = lbl_camera.create_image(
        0, 0, anchor=tk.NW, image=imgtk, tag="live_image"
    )

    # Lower the image so that rectangle is above it
    lbl_camera.tag_lower(image_id)

    lbl_camera.after(10, update_camera_feed)  # Update the camera feed every 10 ms


# Function to monitor button presses
def monitor_gpio():
    global gpio_monitor_task

    if not running:
        return  # Stop further GPIO monitoring if the program is quitting

    try:
        # Detect if we're on the home screen or in the app
        if home_frame.winfo_ismapped():  # If home screen is visible
            # Home screen actions
            if GPIO.input(red_button_pin) == GPIO.LOW:
                quit_program()  # Quit the app (mapped to the red button)
                time.sleep(0.2)  # Debounce delay

            if GPIO.input(blue_button_pin) == GPIO.LOW:
                go_to_app()  # Start the app (mapped to the blue button)
                time.sleep(0.2)  # Debounce delay

            if GPIO.input(green_button_pin) == GPIO.LOW:
                open_docs()  # Open the docs (mapped to the green button)
                time.sleep(0.2)  # Debounce delay

        elif main_frame.winfo_ismapped():  # If the main app screen is visible
            # App screen actions
            if GPIO.input(red_button_pin) == GPIO.LOW:
                quit_program()  # Quit the app (mapped to the red button)
                time.sleep(0.2)  # Debounce delay

            if GPIO.input(blue_button_pin) == GPIO.LOW:
                capture_and_convert_to_svg()  # Capture photo (mapped to the blue button)
                time.sleep(0.2)  # Debounce delay

            if GPIO.input(green_button_pin) == GPIO.LOW:
                if not crop_selected:
                    finalize_crop_zone()  # Finalize crop zone (mapped to the green button)
                else:
                    combine_svgs()  # Combine SVGs
                time.sleep(0.2)  # Debounce delay

            if (
                directory_dialog_open
            ):  # Custom flag to check if directory dialog is open
                if GPIO.input(green_button_pin) == GPIO.LOW:
                    root.event_generate(
                        "<Return>"
                    )  # Simulate Enter key to close the dialog
                    time.sleep(0.2)

    except RuntimeError as e:
        print(f"RuntimeError in monitor_gpio: {e}")
        return  # Exit the function to prevent further errors

    if running:
        gpio_monitor_task = root.after(100, monitor_gpio)


# Function to restart for a new process
def start_another_process():
    global running, image_count, svg_files, output_directory, run_title, crop_selected, rect_id, rectangle_coords
    # Reset global variables
    running = True
    image_count = 0  # Reset image count to 0
    svg_files = []
    output_directory = ""
    run_title = ""
    crop_selected = False
    rectangle_coords = None
    # Clear the crop rectangle if it exists
    if rect_id:
        lbl_camera.delete(rect_id)
        rect_id = None
    # Update the label for Photos Processed to reflect the reset
    lbl_pics_taken.config(text=f"Photos Processed: {image_count}")
    # Reset the button text
    btn_crop.config(text="Confirm Crop Zone")
    # Rerun user variable initialization
    select_directory()


def quit_program():
    global running, gpio_monitor_task
    running = False  # Stop the GPIO monitoring loop

    if gpio_monitor_task is not None:
        root.after_cancel(
            gpio_monitor_task
        )  # Cancel the scheduled GPIO monitoring task
        gpio_monitor_task = None  # Reset the task handle to avoid future issues

    root.quit()  # Quit the Tkinter application


# Create the main window
root = tk.Tk()
root.title("SVG Capture Tool")

# Adjust the window size
root.configure(bg="#B5C689")


# Function to set fullscreen when the window is mapped
def set_fullscreen(event=None):
    root.attributes("-fullscreen", True)


# Bind the set_fullscreen function to the <Map> event
root.bind("<Map>", set_fullscreen)

# ------------- HOME SCREEN FRAME -------------
home_frame = tk.Frame(root, bg="#B5C689")

# Add a welcome label
lbl_welcome = tk.Label(
    home_frame, text="Welcome to the SVG Capture Tool", font=("Arial", 20), bg="#B5C689"
)
lbl_welcome.pack(pady=20)

# Add buttons for the home screen
btn_go_to_app = tk.Button(
    home_frame,
    text="Start App",
    font=("Arial", 16),
    command=go_to_app,
    bg="#2196F3",
    fg="white",
)
btn_go_to_app.pack(pady=10)

btn_open_docs = tk.Button(
    home_frame,
    text="Open Docs",
    font=("Arial", 16),
    command=open_docs,
    bg="#4CAF50",
    fg="white",
)
btn_open_docs.pack(pady=10)

btn_quit = tk.Button(
    home_frame,
    text="Quit",
    font=("Arial", 16),
    command=quit_program,
    bg="red",
    fg="white",
)
btn_quit.pack(pady=10)

# Add instructions label
lbl_instructions = tk.Label(
    home_frame,
    text="Tap an option or use the button that corresponds with its colour.",
    font=("Arial", 20),
    bg="#B5C689",
)
lbl_instructions.pack(pady=20)

# Pack the home frame (this is the first screen the user will see)
home_frame.pack(padx=20, pady=20)

# ------------- APP SCREEN FRAME -------------
# Create a main frame to hold the widgets
main_frame = tk.Frame(root, bg="#B5C689")
main_frame.pack(pady=0, padx=0)

# Create a button to open the directory selection dialog
btn_select_dir = tk.Button(
    main_frame,
    text="Select Directory",
    font=("Arial", 12),
    command=select_directory,
    bg="#FF5722",
    fg="white",
)
btn_select_dir.grid(row=0, column=0, padx=0, pady=0)

# Create a button to capture a photo and convert it to SVG
btn_capture = tk.Button(
    main_frame,
    text="Capture Photo",
    font=("Arial", 12),
    command=capture_and_convert_to_svg,
    bg="#2196F3",
    fg="white",
)
btn_capture.grid(row=1, column=0, padx=0, pady=0)

# Create a button to combine all SVGs
btn_combine_svgs = tk.Button(
    main_frame,
    text="Combine SVGs",
    font=("Arial", 12),
    command=combine_svgs,
    bg="#4CAF50",
    fg="white",
)
btn_combine_svgs.grid(row=2, column=0, padx=0, pady=0)

# Create a button to restart
btn_restart = tk.Button(
    main_frame,
    text="Start Again",
    font=("Arial", 12),
    command=start_another_process,
    bg="#2196F3",
    fg="white",
)
btn_restart.grid(row=3, column=0, padx=0, pady=0)

# Display a label for the number of pictures taken
lbl_pics_taken = tk.Label(
    main_frame,
    text=f"Photos Processed: {image_count}",
    font=("Arial", 12),
    bg="#B5C689",
)
lbl_pics_taken.grid(row=4, column=0, padx=0, pady=0)

# Display a label for the currently selected directory
lbl_selected_dir = tk.Label(
    main_frame,
    text="Output Directory: Not selected",
    font=("Arial", 12),
    bg="#B5C689",
)
# Place the label directly below the live camera feed
lbl_selected_dir.grid(row=4, column=1, padx=0, pady=0)

# Create a button to quit the app
btn_crop = tk.Button(
    main_frame,
    text="Confirm Crop Zone",
    font=("Arial", 12),
    command=handle_crop_button,
    bg="green",
    fg="white",
)
btn_crop.grid(row=2, column=2, padx=0, pady=20)

# Create a button to quit the app
btn_quit = tk.Button(
    main_frame,
    text="Quit",
    font=("Arial", 12),
    command=quit_program,
    bg="red",
    fg="white",
)
btn_quit.grid(row=3, column=2, padx=0, pady=20)

# Create a canvas to show the live camera feed
lbl_camera = tk.Canvas(main_frame, bg="#000000", width=640, height=480)
lbl_camera.grid(row=0, column=1, rowspan=4, padx=0, pady=0)

# Bind mouse events for crop zone selection
lbl_camera.bind("<ButtonPress-1>", start_crop)
lbl_camera.bind("<B1-Motion>", update_crop)
lbl_camera.bind("<ButtonRelease-1>", finish_crop)

# Bind the Enter key to finalize the crop zone
root.bind("<Return>", finalize_crop_zone)

# Create a blank placeholder image
blank_img = Image.new("RGB", (200, 200), color=(0, 0, 0))  # Black image
blank_imgtk = ImageTk.PhotoImage(blank_img)

# Create a label for the last photo taken (with a blank placeholder)
lbl_last_photo_text = tk.Label(
    main_frame, text="Last Photo Processed", font=("Arial", 12), bg="#B5C689"
)
lbl_last_photo_text.grid(row=0, column=2, padx=0, pady=0)
lbl_last_photo = tk.Label(
    main_frame, bg="#000000", width=200, height=200, image=blank_imgtk
)
lbl_last_photo.imgtk = blank_imgtk  # Keep reference to avoid garbage collection
lbl_last_photo.grid(row=0, column=2, rowspan=2, padx=10, pady=10)

# Start the camera
picam2.start()

# Start updating the camera feed
update_camera_feed()

# Initially hide the main_frame
main_frame.pack_forget()

# Start monitoring the GPIO buttons
monitor_gpio()

# Run the GUI main loop
root.mainloop()

# Clean up GPIO before quitting
GPIO.cleanup()
