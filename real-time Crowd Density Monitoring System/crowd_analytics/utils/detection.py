from ultralytics import YOLO
import cv2

# Load YOLOv8 nano model (small and fast)
model = YOLO('yolov8n.pt')  # Make sure yolov8n.pt is downloaded or it will auto-download

def detect_objects(frame):
    # Convert to RGB for YOLO
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    # Run prediction (disable verbose output)
    results = model.predict(source=rgb_frame, conf=0.5, verbose=False)

    person_count = 0

    # Iterate over results
    for result in results:
        for box in result.boxes:
            cls = int(box.cls[0])
            label = model.names[cls]
            if label == 'person':
                person_count += 1

                # Draw bounding box on the original frame
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                conf = float(box.conf[0])
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(
                    frame,
                    f'{label} {conf:.2f}',
                    (x1, y1 - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (0, 255, 0),
                    2
                )

    return frame, person_count
