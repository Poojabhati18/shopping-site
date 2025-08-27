import os

# Current folder
folder = "."

for filename in os.listdir(folder):
    if filename.lower().endswith((".jpeg", ".jpg")):
        file_path = os.path.join(folder, filename)
        os.remove(file_path)
        print(f"Deleted: {filename}")

print("✅ All JPEG files deleted.")
