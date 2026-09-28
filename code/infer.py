# python -m venv .enc
# source .enc/bin/activate

# pip install huggingface_hub
# pip install numpy
# pip install onnxruntime
# pip install Pillow
##############################

# 16 mn / 42650 images


import csv
import json
import numpy as np
import onnxruntime as ort
from PIL import Image
from pathlib import Path
import argparse
import shutil


# Models repository
from huggingface_hub import snapshot_download
path = snapshot_download(repo_id="ENC-PSL/BSICLE")
print(path)


# Parameters
MODELS = [
    #"mobilenetv2",
    "mobilenetv3_large",
    #"mobilenetv3_small",
    #"mobilevitv2",
]
ARTEFACTS_DIR = Path(path)

model_name = "mobilenetv3_large"
run = ARTEFACTS_DIR / model_name

# Inference results
results= "inferences.csv"

# Inference threshold
threshold = 0.75 # float(cfg.get("threshold", 0.5))

# Images source
# ask for a folder as a parameter from the user input
def get_image_paths(image_folder: str) -> dict:
    """Get all image paths recursively from a folder and its subfolders.

    :param image_folder: path to the root folder containing images
    :type image_folder: str
    :return: dictionary mapping image paths to Path objects
    :rtype: dict
    """
    image_folder = Path(image_folder)
    if not image_folder.exists():
        raise FileNotFoundError(f"Image folder not found: {image_folder}")

    extensions = ("*.jpg", "*.jpeg", "*.png", "*.tif", "*.tiff", "*.JPG", "*.JPEG", "*.PNG", "*.TIF", "*.TIFF")
    image_paths = {}
    for ext in extensions:
        for image_path in image_folder.rglob(ext):
            if image_path.is_file():
                image_paths[str(image_path)] = image_path
    return image_paths  

def get_arguments() -> argparse.Namespace:
    """Get the arguments from the command line."""
    parser = argparse.ArgumentParser(description="Run inference on a single model and return the results.")
    parser.add_argument("--image_folder", type=str, required=True, help="Path to the folder containing the images")
    return parser.parse_args()

def softmax(logits: np.ndarray) -> np.ndarray:
    """Softmax function to convert logits to probabilities.

    :param logits: logits array
    :type logits: np.ndarray
    :return: probabilities array
    :rtype: np.ndarray
    """
    logits = logits.astype(np.float32)
    exp = np.exp(logits - logits.max())
    return exp / exp.sum()


def load_json(path: Path) -> dict:
    """Load a JSON file and return its content as a dictionary.

    :param path: path to the JSON file
    :type path: Path
    :return: content of the JSON file as a dictionary
    :rtype: dict
    """
    if not path.exists():
        raise FileNotFoundError(f"File not founded: {path}")
    return json.loads(path.read_text())


def preprocess_image(image_path: Path, pre: dict) -> np.ndarray:
    """Preprocess the image according to the provided configuration.

    :param image_path: path to the image file
    :type image_path: Path
    :param pre: preprocessing configuration (expects keys 'img_size', 'mean', 'std
    :type pre: dict
    :return: preprocessed image as a numpy array ready for model input
    :rtype: np.ndarray
    """
    if not image_path.exists():
        raise FileNotFoundError(f"Image not founded: {image_path}")

    img_size = pre["img_size"]
    mean = np.array(pre["mean"], dtype=np.float32)
    std = np.array(pre["std"], dtype=np.float32)

    img = Image.open(image_path).convert("RGB").resize((img_size, img_size))

    x = np.asarray(img).astype(np.float32) / 255.0
    x = (x - mean) / std
    x = x.transpose(2, 0, 1)[None].astype(np.float32)

    return x


def predict(image_path: Path) -> dict:
    global model_name, run, cfg, positive_label, negative_label, threshold

    """Run inference on a single model and return the results.

    :param image_path: path to the image file to test
    :type image_path: Path
    :return: dictionary containing the prediction results and probabilities
    :rtype: dict
    """
    

    model_path = run / "onnx" / "model.onnx"
    if not model_path.exists():
        raise FileNotFoundError(f"ONNX model not founded: {model_path}")

    x = preprocess_image(image_path, pre)

    sess = ort.InferenceSession(str(model_path))

    input_name = cfg.get("input_name")
    if input_name is None:
        input_name = sess.get_inputs()[0].name

    output = sess.run(None, {input_name: x})[0]

    # Cas standard : shape (1, 2)
    logits = output[0]

    probs = softmax(logits)

    p_illu = float(probs[1])

    label = positive_label if p_illu >= threshold else negative_label

    return {
        "model": model_name,
        "image": str(image_path),
        "label": label,
        "p_illustration": p_illu,
        "probs": probs.tolist(),
        "threshold": threshold,
    }


def main():
    """Main function to run the tests on all models and images."""
    args = get_arguments() 

    print("=" * 80)
    print(f"Image folder provided: {args.image_folder}")

    IMAGE_PATHS = get_image_paths(args.image_folder)
    print(f"Number of images to process: {len(IMAGE_PATHS)}")

    print("Threshold:", threshold)

    # Create results folder if it doesn't exist
    results_dir = Path("./results")
    results_dir.mkdir(exist_ok=True)
    csv_file_path = results_dir / results
    # create folder for copying the classified images
    non_illustrations_dir = results_dir / "non_illustrations"
    illustrations_dir = results_dir / "illustrations"
    non_illustrations_dir.mkdir(exist_ok=True) 
    illustrations_dir.mkdir(exist_ok=True) 

    # Open CSV file and write header and rows
    fieldnames = ["image", "model", "label", "p_illustration", "threshold", "probs"]

    with open(csv_file_path, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for _, image_path in IMAGE_PATHS.items():
            print("=" * 80)
            print(f"Image: {image_path}")

            try:
                result = predict(image_path)
                # copy the image file to the right folder based on the label
                if result["label"] == "illumination":
                    shutil.copy(str(image_path), str(illustrations_dir / image_path.name))
                else:
                    shutil.copy(str(image_path), str(non_illustrations_dir / image_path.name))

                print(
                    f"{result['model']:<20} "
                    f"=> {result['label']:<18} "
                    f"p_illu={result['p_illustration']:.4f} "
                    f"probs={result['probs']}"
                )

                writer.writerow({
                    "image": str(image_path),
                    "model": model_name,
                    "label": result["label"],
                    "p_illustration": result["p_illustration"],
                    "threshold": result["threshold"],
                    "probs": json.dumps(result["probs"]),
                })

            except Exception as e:
                print(f"{model_name:<20} → ERROR: {e}")
                writer.writerow({
                    "image": str(image_path),
                    "model": model_name,
                    "label": "ERROR",
                        "p_illustration": "",
                        "threshold": "",
                        "probs": str(e),
                    })


    print(f"\nResults successfully written to {csv_file_path}")


if __name__ == "__main__":
    cfg = load_json(run / "inference_config.json")
    pre = load_json(run / "preprocess.json")
    positive_label = cfg.get("positive_label", "illumination")
    negative_label = cfg.get("negative_label", "non_illumination")

    main()
