import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog
from PIL import Image, ImageTk
import cv2
import numpy as np
import subprocess
import os
import tempfile
from picamera2 import Picamera2
import RPi.GPIO as GPIO
import time
import webbrowser

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
running = True
image_count = 0
svg_files = []
output_directory = ""
run_title = ""
directory_dialog_open = False
gpio_monitor_task = None

# Function to switch to the main app screen
def go_to_app():
    home_frame.pack_forget()
    main_frame.pack(padx=0, pady=0)
    
    # Show the directory label
    lbl_selected_dir.place(x=4, y=500)

    # Prompt the user to select a directory on app startup
    select_directory()

# Function to allow the user to open the docs
def open_docs():
    webbrowser.open("https://docs.example.com")
    

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
    last_img = last_img.resize((200, 200))
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
    
    # Set an initial Y position and choose vertical spacing
    y_position = 0
    vertical_spacing = 500

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
                
                # Wrap each SVG content in a <g> element and translate its position
                translated_svg_body = f'<g transform="translate(0, {y_position})">\n{svg_body}\n</g>\n'
                combined_svg.write(translated_svg_body)

                # Update the Y position for the next SVG
                y_position += vertical_spacing

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
    global output_directory, run_title, image_count
    directory_dialog_open = True
    directory = filedialog.askdirectory(title="Choose a folder to save your files")
    run_title = simpledialog.askstring(title="Folder Name", prompt="What do you want to name the folder your files are stored in? (ex. Run 1)")
    directory_dialog_open = False
    if directory:
        output_directory = os.path.join(directory, run_title)
        lbl_selected_dir.config(text=f"Output Directory: {output_directory}")
        
        # Ensure the photos and svgs directories exist
        photos_dir = os.path.join(output_directory, "photos")
        os.makedirs(photos_dir, exist_ok=True)
        
        # Check the existing files in the photos directory and reset image_count accordingly
        existing_images = [f for f in os.listdir(photos_dir) if f.endswith('.jpg')]
        image_count = len(existing_images)  # Set the image_count based on existing images
        
        # Update the label for Photos Processed after selecting the directory
        lbl_pics_taken.config(text=f"Photos Processed: {image_count}")
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
                combine_svgs()  # Combine SVGs (mapped to the green button)
                time.sleep(0.2)  # Debounce delay

            if directory_dialog_open:  # Custom flag to check if directory dialog is open
                if GPIO.input(green_button_pin) == GPIO.LOW:
                    root.event_generate('<Return>')  # Simulate Enter key to close the dialog
                    time.sleep(0.2)

    except RuntimeError as e:
        print(f"RuntimeError in monitor_gpio: {e}")
        return  # Exit the function to prevent further errors

    if running:
        gpio_monitor_task = root.after(100, monitor_gpio)


        
# Function to restart for a new process
def start_another_process():
    global running, image_count, svg_files, output_directory, run_title
    
    # Reset global variables
    running = True
    image_count = 0  # Reset image count to 0
    svg_files = []
    output_directory = ""
    run_title = ""
    
    # Update the label for Photos Processed to reflect the reset
    lbl_pics_taken.config(text=f"Photos Processed: {image_count}")
    
    # Rerun user variable initialization
    select_directory() 

    


def quit_program():
    global running, gpio_monitor_task
    running = False  # Stop the GPIO monitoring loop

    if gpio_monitor_task is not None:
        root.after_cancel(gpio_monitor_task)  # Cancel the scheduled GPIO monitoring task
        gpio_monitor_task = None  # Reset the task handle to avoid future issues

    root.quit()     # Quit the Tkinter application





# Create the main window
root = tk.Tk()
root.title("SVG Capture Tool")

# Adjust the window size
root.geometry("1024x500")
root.configure(bg="#B5C689")

# ------------- HOME SCREEN FRAME -------------
home_frame = tk.Frame(root, bg="#B5C689")

# Add a welcome label
lbl_welcome = tk.Label(home_frame, text="Welcome to the SVG Capture Tool", font=("Arial", 20), bg="#B5C689")
lbl_welcome.pack(pady=20)

# Add buttons for the home screen
btn_go_to_app = tk.Button(home_frame, text="Start App", font=("Arial", 16), command=go_to_app, bg="#2196F3", fg="white")
btn_go_to_app.pack(pady=10)

btn_open_docs = tk.Button(home_frame, text="Open Docs", font=("Arial", 16), command=open_docs, bg="#4CAF50", fg="white")
btn_open_docs.pack(pady=10)

btn_quit = tk.Button(home_frame, text="Quit", font=("Arial", 16), command=quit_program, bg="red", fg="white")
btn_quit.pack(pady=10)

# Add a welcome label
lbl_instructions = tk.Label(home_frame, text="Tap an option or use the button the corresponds with its colour.", font=("Arial", 20), bg="#B5C689")
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
    root,
    text=f"Output Directory: {output_directory}",
    font=("Arial", 12),
    bg="#B5C689",
)
lbl_selected_dir.place(x=4, y=500)
lbl_selected_dir.place_forget()

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


# Create a label to show the live camera feed on the right side
lbl_camera = tk.Label(main_frame, bg="#000000", width=640, height=480)
lbl_camera.grid(row=0, column=1, rowspan=4, padx=0, pady=0)

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
lbl_last_photo.grid(row=0, column=2, rowspan=4, padx=10, pady=10)

# Start the camera
picam2.start()

# Start updating the camera feed
update_camera_feed()

# Initially hide the main_frame
main_frame.pack_forget()

# Start monitoring the GPIO buttons
monitor_gpio()

root.attributes("-fullscreen", True)

# Run the GUI main loop
root.mainloop()

print("Cleaning up GPIO...")
GPIO.cleanup()  # Clean up GPIO before quitting
