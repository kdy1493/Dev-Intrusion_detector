import cv2
RTSP_URL = f"rtsp://admin:kistWRLi^2rc@192.168.5.23:554/ISAPI/Streaming/channels/101"
#RTSP_URL = "rtsp://admin:kistWRLi^2rc@161.122.42.33:9302/ISAPI/Streaming/channels/101"
cap = cv2.VideoCapture(RTSP_URL)
if not cap.isOpened():    
    print("Error: Unable to open RTSP stream.")    
    exit()

print("RTSP stream opened successfully. Press 'q' to exit.")
x_start, y_start = 0, 0
x_end, y_end = 1920-x_start, 1080
while True:    
    ret, frame = cap.read()     
    if not ret:        
        print("Error: Failed to receive frame. Exiting...")        
        break    
    height, width, channels = frame.shape      
    # print(f"Frame Size: {width}x{height}, Channels: {channels}")    
    # 프레임을 자르기 (Crop)    
    cropped_frame = frame[y_start:y_end, x_start:x_end]
    cv2.imshow("Cropped RTSP Stream", cropped_frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):        
        break
cap.release()
cv2.destroyAllWindows()