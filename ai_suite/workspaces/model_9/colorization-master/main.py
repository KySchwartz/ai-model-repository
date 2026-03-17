import argparse
import torch
import numpy as np
import cv2
from colorizers import eccv16, siggraph17

def load_model(model_name):
    if model_name.lower() == "eccv16":
        print("Loading ECCV16 model...")
        return eccv16(pretrained=True).eval()
    elif model_name.lower() == "siggraph17":
        print("Loading SIGGRAPH17 model...")
        return siggraph17(pretrained=True).eval()
    else:
        raise ValueError("Model must be 'eccv16' or 'siggraph17'")

def colorize_image(model, input_path, output_path):
    # Load grayscale image
    img_gray = cv2.imread(input_path, cv2.IMREAD_GRAYSCALE)
    if img_gray is None:
        raise FileNotFoundError(f"Could not load image: {input_path}")

    img_gray = img_gray.astype("float32") / 255.0
    img_gray = cv2.cvtColor(img_gray, cv2.COLOR_GRAY2RGB)

    # Convert to Lab
    img_lab = cv2.cvtColor(img_gray, cv2.COLOR_RGB2LAB)
    L = img_lab[:, :, 0]

    tens_l = torch.from_numpy(L).unsqueeze(0).unsqueeze(0)
    tens_l = tens_l.float()

    # Run model
    with torch.no_grad():
        out_ab = model(tens_l).cpu().numpy()[0].transpose((1, 2, 0))

    # Combine L + predicted AB
    out_lab = np.concatenate((L[:, :, np.newaxis], out_ab), axis=2)
    out_bgr = cv2.cvtColor(out_lab.astype("float32"), cv2.COLOR_Lab2BGR)
    out_bgr = np.clip(out_bgr, 0, 1)

    cv2.imwrite(output_path, (out_bgr * 255).astype("uint8"))
    print(f"Saved colorized image to {output_path}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Path to grayscale input image")
    parser.add_argument("--output", required=True, help="Path to save colorized output")
    parser.add_argument("--model", default="eccv16", help="eccv16 or siggraph17")
    args = parser.parse_args()

    model = load_model(args.model)
    colorize_image(model, args.input, args.output)

if __name__ == "__main__":
    main()