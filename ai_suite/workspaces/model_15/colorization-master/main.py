# main.py (Inside the colorization-master folder in your zip)
import torch
from PIL import Image
# Assuming the 'colorizers' folder is in the same directory
from colorizers import eccv16, siggraph17, util 

# Load model once at the top for efficiency
model = eccv16(pretrained=True).eval()

def handle_request(input_path):
    # input_path is passed from Django (e.g., 'temp_uploads/my_photo.jpg')
    full_path = f"/app/media_shared/{input_path}"
    
    # 1. Load and process image
    img = util.load_img(full_path)
    (tens_l_orig, tens_l_rs) = util.preprocess_img(img, HW=(256,256))
    
    # 2. Run model
    out_img = model(tens_l_rs).data.cpu()
    
    # 3. Post-process
    colorized_res = util.postprocess_tens(tens_l_orig, out_img)
    
    # 4. Convert numpy to PIL Image to satisfy our 'save' logic
    final_image = Image.fromarray((colorized_res * 255).astype('uint8'))
    
    return final_image