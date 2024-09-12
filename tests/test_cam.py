from picamera2 import Picamera2
import cv2

# Initialize the camera
picam2 = Picamera2()

# Configure the camera for preview (low-resolution mode)
picam2.preview_configuration.main.size = (640, 480)  # You can change the resolution if needed
picam2.preview_configuration.main.format = "RGB888"  # Set the format to RGB
picam2.configure("preview")

# Start the camera
picam2.start()

# Display the live feed
while True:
    # Capture the frame from the camera
    frame = picam2.capture_array()

    # Display the frame in a window
    cv2.imshow("Live Camera Feed", frame)

    # Check if the 'q' key is pressed to exit the loop
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# Release resources
cv2.destroyAllWindows()

# Stop the camera
picam2.stop()

