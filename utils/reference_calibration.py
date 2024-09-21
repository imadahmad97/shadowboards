import cv2
import os
import json
from picamera2 import Picamera2
from tkinter import filedialog, Tk
import matplotlib.pyplot as plt

# Initialize the camera
picam2 = Picamera2()
picam2.configure(picam2.create_still_configuration(main={"size": (640, 480)}))


# Function to capture the reference image
def capture_reference_image():
    root = Tk()
    root.withdraw()  # Hide the main window
    output_directory = filedialog.askdirectory(
        title="Select Directory for Reference Image"
    )
    root.destroy()

    if not output_directory:
        print("No directory selected, exiting.")
        return None

    reference_image_path = os.path.join(output_directory, "reference_object.jpg")

    # Capture the reference image
    picam2.start()
    picam2.capture_file(reference_image_path)
    picam2.stop()

    return reference_image_path


# Function to manually crop the reference object
def crop_reference_object(image):
    r = cv2.selectROI(
        "Select the reference object", image, fromCenter=False, showCrosshair=True
    )
    if r:
        cropped_image = image[
            int(r[1]) : int(r[1] + r[3]), int(r[0]) : int(r[0] + r[2])
        ]
        cv2.destroyAllWindows()
        return cropped_image
    return image


# Function to calculate pixels per cm from the cropped reference object
def calculate_pixels_per_cm(cropped_image, known_size_cm):
    # Convert the image to grayscale
    gray = cv2.cvtColor(cropped_image, cv2.COLOR_BGR2GRAY)

    # Apply binary thresholding to detect contours
    _, binary = cv2.threshold(gray, 128, 255, cv2.THRESH_BINARY_INV)
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # Find the bounding box of the largest contour (assumed to be the reference object)
    largest_contour = max(contours, key=cv2.contourArea)
    x, y, w, h = cv2.boundingRect(largest_contour)

    # Measure the width or height of the object in pixels
    reference_object_pixels = max(w, h)  # Take the larger dimension

    # Calculate the pixels-per-cm ratio
    pixels_per_cm = reference_object_pixels / known_size_cm
    print(f"Pixels per cm: {pixels_per_cm}")
    return pixels_per_cm


# Save calibration data to a file
def save_calibration_data(pixels_per_cm, output_directory):
    calibration_data = {"pixels_per_cm": pixels_per_cm}
    calibration_file_path = os.path.join(output_directory, "calibration_data.json")

    with open(calibration_file_path, "w") as f:
        json.dump(calibration_data, f)

    print(f"Calibration data saved to: {calibration_file_path}")


if __name__ == "__main__":
    known_size_cm = float(
        input("Enter the real-world size of the reference object (in cm): ")
    )
    reference_image_path = capture_reference_image()

    if reference_image_path:
        # Load the reference image
        reference_image = cv2.imread(reference_image_path)

        # Crop the reference object manually
        cropped_image = crop_reference_object(reference_image)

        # Calculate the pixels per cm from the cropped image
        pixels_per_cm = calculate_pixels_per_cm(cropped_image, known_size_cm)

        # Save the calibration data
        save_calibration_data(pixels_per_cm, os.path.dirname(reference_image_path))
