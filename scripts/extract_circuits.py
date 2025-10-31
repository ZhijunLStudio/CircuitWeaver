import os
import json
import cairosvg
from bs4 import BeautifulSoup

# --- 配置 ---
ROOT_DIR = 'schemdraw.readthedocs.io'
SEARCH_DIR = os.path.join(ROOT_DIR, 'en', 'stable')
OUTPUT_DIR = 'processed_circuits'
PAIRS_SUBDIR = 'pairs'
UNPAIRED_SUBDIR = 'unpaired_code'
MANIFEST_FILE = 'manifest.json'

def setup_output_directory():
    """创建所有需要的输出目录"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(os.path.join(OUTPUT_DIR, PAIRS_SUBDIR), exist_ok=True)
    os.makedirs(os.path.join(OUTPUT_DIR, UNPAIRED_SUBDIR), exist_ok=True)
    print(f"Output directory '{OUTPUT_DIR}' is ready.")

def parse_html_file(file_path):
    """
    解析单个HTML文件，提取成对的代码-图像和独立的无图像代码块。
    返回两个列表：pairs 和 unpaired_codes
    """
    pairs = []
    unpaired_codes = []
    
    with open(file_path, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f, 'lxml')

    source_html_path = os.path.relpath(file_path, start='.')

    # ==================== 逻辑修正开始 ====================

    # 策略 1: 优先查找 jupyter_cell，因为它们是明确的输入/输出对
    processed_code_tags = set()
    jupyter_cells = soup.find_all('div', class_='jupyter_cell')
    
    for cell in jupyter_cells:
        code_tag = cell.select_one('div.cell_input pre')
        img_tag = cell.select_one('div.cell_output img')

        if not code_tag:
            continue
            
        processed_code_tags.add(code_tag) # 标记这个代码块已经被处理
        code = code_tag.get_text().strip()

        # 检查是否是有效的代码-图像对
        if img_tag and img_tag.get('src'):
            relative_img_path = img_tag['src']
            html_dir = os.path.dirname(file_path)
            abs_svg_path = os.path.normpath(os.path.join(html_dir, relative_img_path))
            
            if os.path.exists(abs_svg_path):
                pairs.append({
                    'source_html': source_html_path,
                    'code': code,
                    'svg_path': os.path.relpath(abs_svg_path, start='.')
                })
            else:
                # 图像文件不存在，当作无配对代码处理
                unpaired_codes.append({ 'source_html': source_html_path, 'code': code })
        else:
            # jupyter_cell 中有代码但没有图像输出
            unpaired_codes.append({ 'source_html': source_html_path, 'code': code })

    # 策略 2: 查找所有其他代码块 (例如 <div class="highlight-python">)
    # 确保它们没有在 jupyter_cell 中被处理过
    all_other_code_blocks = soup.select('div.highlight pre')
    for code_tag in all_other_code_blocks:
        if code_tag not in processed_code_tags:
            code = code_tag.get_text().strip()
            # 避免空的代码块
            if code:
                unpaired_codes.append({ 'source_html': source_html_path, 'code': code })

    # ===================== 逻辑修正结束 ====================

    return pairs, unpaired_codes


def main():
    """主函数，遍历、解析、转换并保存所有数据"""
    setup_output_directory()
    
    manifest_data = []
    pair_counter = 0
    unpaired_counter = 0

    print("\nStarting HTML file traversal and parsing...")
    for root, _, files in os.walk(SEARCH_DIR):
        for file in files:
            if file.endswith('.html'):
                file_path = os.path.join(root, file)
                
                try:
                    pairs, unpaired_codes = parse_html_file(file_path)
                except Exception as e:
                    print(f"  [ERROR] Could not parse {file_path}: {e}")
                    continue

                # --- 处理成对的数据 ---
                for pair in pairs:
                    pair_counter += 1
                    pair_id = f"pair_{pair_counter:04d}"
                    item_dir = os.path.join(OUTPUT_DIR, PAIRS_SUBDIR, pair_id)
                    os.makedirs(item_dir, exist_ok=True)
                    
                    code_path = os.path.join(item_dir, 'source.py')
                    with open(code_path, 'w', encoding='utf-8') as f_code:
                        f_code.write(pair['code'])
                        
                    png_path = os.path.join(item_dir, 'image.png')
                    try:
                        cairosvg.svg2png(url=pair['svg_path'], write_to=png_path, background_color="white")
                    except Exception as e:
                        print(f"  [WARN] Failed to convert SVG {pair['svg_path']} for {pair_id}. Error: {e}")
                        png_path = None
                    
                    manifest_data.append({
                        'id': pair_id,
                        'type': 'pair',
                        'source_html': pair['source_html'].replace('\\', '/'),
                        'code_path': os.path.relpath(code_path, start=OUTPUT_DIR).replace('\\', '/'),
                        'image_path': os.path.relpath(png_path, start=OUTPUT_DIR).replace('\\', '/') if png_path else None
                    })

                # --- 处理独立的无图像代码 ---
                for unpaired in unpaired_codes:
                    unpaired_counter += 1
                    code_id = f"code_{unpaired_counter:04d}"
                    code_path = os.path.join(OUTPUT_DIR, UNPAIRED_SUBDIR, f"{code_id}.py")
                    with open(code_path, 'w', encoding='utf-8') as f_code:
                        f_code.write(unpaired['code'])
                    
                    manifest_data.append({
                        'id': code_id,
                        'type': 'unpaired_code',
                        'source_html': unpaired['source_html'].replace('\\', '/'),
                        'code_path': os.path.relpath(code_path, start=OUTPUT_DIR).replace('\\', '/')
                    })
    
    manifest_path = os.path.join(OUTPUT_DIR, MANIFEST_FILE)
    with open(manifest_path, 'w', encoding='utf-8') as f_manifest:
        json.dump(manifest_data, f_manifest, indent=2, ensure_ascii=False)

    print("\n--- Extraction Complete ---")
    print(f"  - Found and processed {pair_counter} code-image pairs.")
    print(f"  - Found and saved {unpaired_counter} unpaired code snippets.")
    print(f"  - All results are saved in the '{OUTPUT_DIR}' directory.")
    print(f"  - An index of all items has been created at '{manifest_path}'.")

if __name__ == '__main__':
    main()