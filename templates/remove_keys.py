import os

folder_path = r'C:\Users\digvi\shopping-site\templates'  # your project folder
api_key_to_remove = 'AIzaSyAMdIocoBpmm7sAXVKIvI7ggodNTCNdbCM'

print("Starting to scan files...")

found_any = False
for subdir, dirs, files in os.walk(folder_path):
    for file in files:
        if file.endswith('.html'):
            file_path = os.path.join(subdir, file)
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            new_content = content.replace(api_key_to_remove, '')
            if new_content != content:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                print(f"Removed key from {file_path}")
                found_any = True

if not found_any:
    print("No instances of the API key were found in your .html files.")

print("Done scanning all files.")
