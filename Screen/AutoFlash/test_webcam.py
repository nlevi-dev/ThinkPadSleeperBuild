#!/usr/bin/env python3
import cv2

cap = cv2.VideoCapture(2)
cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 1)
cap.set(cv2.CAP_PROP_EXPOSURE, 10000)
cap.set(cv2.CAP_PROP_GAIN, 255)
cap.set(cv2.CAP_PROP_BRIGHTNESS, 255)
cap.set(cv2.CAP_PROP_CONTRAST, 255)
for _ in range(5): cap.read()
ret, frame = cap.read()
cap.release()

if not ret:
    print("failed to capture")
else:
    cv2.imwrite("reference.png", frame)
    print("saved reference.png")
