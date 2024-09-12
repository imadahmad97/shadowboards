import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk
import cv2
import numpy as np
import subprocess
import os
import tempfile
from picamera2 import Picamera2
import RPi.GPIO as GPIO
import time

# Initialize the camera
picam2 = Picamera2()

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
image_count = 0
svg_files = []
output_directory = ""


# Function to capture image and convert to SVG
def capture_and_convert_to_svg():
    global image_count, output_directory

    if not output_directory:
        messagebox.showerror("Error", "Please select an output directory first.")
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

    # Load the last captured image and display it on the label
    last_img = Image.open(image_path)
    last_img = last_img.resize((200, 200))  # Resize for display
    last_imgtk = ImageTk.PhotoImage(last_img)

    lbl_last_photo.imgtk = last_imgtk  # Keep a reference to avoid garbage collection
    lbl_last_photo.configure(image=last_imgtk)

    # Load the captured image
    image = cv2.imread(image_path)

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

    # Save the mask to a temporary in-memory PGM file
    with tempfile.NamedTemporaryFile(suffix=".pgm", delete=True) as temp_pgm:
        cv2.imwrite(temp_pgm.name, mask_inv)

        # Run potrace using the temporary PGM file
        subprocess.run(["potrace", "-s", "-o", svg_path, temp_pgm.name])

    # Add the SVG path to the list for combining later
    svg_files.append(svg_path)

    lbl_pics_taken.config(text=f"Photos Processed: {image_count}")


# Function to combine all SVGs into a single file
def combine_svgs():
    global svg_files, output_directory

    if not svg_files:
        messagebox.showerror("Error", "No SVG files to combine.")
        return

    combined_svg_path = os.path.join(output_directory, "combined_output.svg")

    # Create a header for the combined SVG file
    svg_header = """<svg xmlns="http://www.w3.org/2000/svg" version="1.1">\n"""
    svg_footer = """</svg>"""

    # Open the combined SVG file
    with open(combined_svg_path, "w") as combined_svg:
        combined_svg.write(svg_header)

        # Append each SVG content into the combined file
        for svg_file in svg_files:
            with open(svg_file, "r") as f:
                svg_content = f.read()

                # Extract everything inside the <svg> tags
                start_index = svg_content.find("<svg")
                end_index = svg_content.find(">", start_index) + 1
                svg_body = svg_content[end_index:]

                # Remove the closing </svg> tag from the body
                svg_body = svg_body.replace("</svg>", "")

                combined_svg.write(svg_body)

        combined_svg.write(svg_footer)

    messagebox.showinfo(
        "Success", f"All SVGs combined and saved as {combined_svg_path}"
    )

    # Reset the image count and svg files for the next set
    image_count = 0
    svg_files = []
    lbl_pics_taken.config(text=f"Photos Processed: {image_count}")


# Function to select a directory
def select_directory():
    global output_directory
    directory = filedialog.askdirectory()
    if directory:
        output_directory = directory
        messagebox.showinfo(
            f"Selected Directory: {directory}", f"Selected Directory: {directory}"
        )
    else:
        lbl_selected_dir.config(text="No Directory Selected")


# Function to update the live camera feed in the GUI
def update_camera_feed():
    frame = picam2.capture_array()  # Capture a frame from the camera
    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)  # Convert the frame to RGB

    img = Image.fromarray(frame)  # Convert frame to a PIL image
    imgtk = ImageTk.PhotoImage(image=img)  # Convert PIL image to ImageTk format

    lbl_camera.imgtk = imgtk  # Keep a reference to avoid garbage collection
    lbl_camera.configure(image=imgtk)  # Update the label with the new image

    lbl_camera.after(10, update_camera_feed)  # Update the camera feed every 10 ms


# Function to monitor button presses
def monitor_gpio():
    # Check if the red button (Quit) is pressed
    if GPIO.input(red_button_pin) == GPIO.LOW:
        quit_program()  # Clean up GPIO and quit the app
        time.sleep(0.2)  # Debounce delay

    # Check if the blue button (Capture Photo) is pressed
    if GPIO.input(blue_button_pin) == GPIO.LOW:
        capture_and_convert_to_svg()  # Calls the function to capture a photo
        time.sleep(0.2)  # Debounce delay

    # Check if the green button (Combine SVGs) is pressed
    if GPIO.input(green_button_pin) == GPIO.LOW:
        combine_svgs()  # Calls the function to combine SVGs
        time.sleep(0.2)  # Debounce delay

    # Continuously check GPIO state
    root.after(100, monitor_gpio)  # Schedule this function to run every 100ms


# Function to end the program on quitting
def quit_program():
    GPIO.cleanup()  # Clean up GPIO
    root.quit()  # Quit the Tkinter application


# Create the main window
root = tk.Tk()
root.title("SVG Capture Tool")

# Adjust the window size
root.geometry("1200x650")
root.configure(bg="#B5C689")

# Create a main frame to hold the widgets
main_frame = tk.Frame(root, bg="#B5C689")
main_frame.pack(pady=20, padx=20)

# Create a button to open the directory selection dialog
btn_select_dir = tk.Button(
    main_frame,
    text="Select Directory",
    font=("Arial", 12),
    command=select_directory,
    bg="#FF5722",
    fg="white",
)
btn_select_dir.grid(row=1, column=0, padx=10, pady=10)

# Create a button to capture a photo and convert it to SVG
btn_capture = tk.Button(
    main_frame,
    text="Capture Photo",
    font=("Arial", 12),
    command=capture_and_convert_to_svg,
    bg="#2196F3",
    fg="white",
)
btn_capture.grid(row=2, column=0, padx=10, pady=10)

# Display a label for the number of pictures taken
lbl_pics_taken = tk.Label(
    main_frame,
    text=f"Photos Processed: {image_count}",
    font=("Arial", 12),
    bg="#f0f0f0",
)
lbl_pics_taken.grid(row=4, column=0, padx=10, pady=10)

# Create a button to combine all SVGs
btn_combine_svgs = tk.Button(
    main_frame,
    text="Combine SVGs",
    font=("Arial", 12),
    command=combine_svgs,
    bg="#4CAF50",
    fg="white",
)
btn_combine_svgs.grid(row=3, column=0, padx=10, pady=10)

# Create a button to quit the app
btn_quit = tk.Button(
    main_frame,
    text="Quit",
    font=("Arial", 12),
    command=quit_program,
    bg="red",
    fg="white",
)
btn_quit.grid(row=5, column=0, padx=10, pady=10)


# Create a label to show the live camera feed on the right side
lbl_camera = tk.Label(main_frame, bg="#000000", width=640, height=480)
lbl_camera.grid(row=0, column=1, rowspan=4, padx=10, pady=10)

# Create a blank placeholder image
blank_img = Image.new("RGB", (200, 200), color=(0, 0, 0))  # Black image
blank_imgtk = ImageTk.PhotoImage(blank_img)

# Create a label for the last photo taken (with a blank placeholder)
lbl_last_photo_text = tk.Label(
    main_frame, text="Last Photo Processed", font=("Arial", 12), bg="#B5C689"
)
lbl_last_photo_text.grid(row=0, column=2, padx=10, pady=10)
lbl_last_photo = tk.Label(
    main_frame, bg="#000000", width=200, height=200, image=blank_imgtk
)
lbl_last_photo.imgtk = blank_imgtk  # Keep reference to avoid garbage collection
lbl_last_photo.grid(row=0, column=2, rowspan=4, padx=10, pady=10)

# Start the camera
picam2.start()

# Start updating the camera feed
update_camera_feed()

# Start monitoring the GPIO buttons
monitor_gpio()

# Run the GUI main loop
root.mainloop()
