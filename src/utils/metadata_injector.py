# src/utils/metadata_injector.py
import os

def generate_metadata_code(image_filename: str, metadata_filename: str) -> str:
    # 这个函数保持不变，因为它已经很完美了
    return f"""
# --- METADATA EXTRACTION ---
try:
    import json
    import os

    # 'd' is the finalized Drawing object from the script above.
    # The working directory is already the sandbox, so no need for output_dir
    output_path = "{metadata_filename}"

    metadata = {{"components": {{}}, "connections": {{}}}}
    element_counter = {{}}
    connection_nodes = {{}}

    for element in d.elements:
        element_type = type(element).__name__
        count = element_counter.get(element_type, 0) + 1
        element_counter[element_type] = count
        element_id = f"{{element_type}}_{{count}}"
        
        bbox = element.get_bbox()
        
        metadata["components"][element_id] = {{
            'type': element_type,
            'bounding_box': {{
                'xmin': round(bbox.xmin, 3), 'ymin': round(bbox.ymin, 3),
                'xmax': round(bbox.xmax, 3), 'ymax': round(bbox.ymax, 3)
            }},
            'anchors': {{}}
        }}
        
        for anchor_name in element.anchors.keys():
            try:
                abs_coord = getattr(element, anchor_name)
                x, y = round(abs_coord.x, 3), round(abs_coord.y, 3)
                coord_key = f"({{x}}, {{y}})"
                metadata["components"][element_id]['anchors'][anchor_name] = {{'x': x, 'y': y}}
                if coord_key not in connection_nodes:
                    connection_nodes[coord_key] = []
                connection_nodes[coord_key].append(f"{{element_id}}.{{anchor_name}}")
            except Exception:
                pass

    metadata['connections'] = {{k: v for k, v in connection_nodes.items() if len(v) > 1}}
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2)
    
    print(f"\\nSuccessfully generated metadata file: '{{output_path}}'")

except NameError:
    print("\\nError: The 'd' (Drawing) object was not found for metadata extraction.")
except Exception as e:
    print(f"\\nAn error occurred during metadata extraction: {{e}}")
# --- END OF METADATA EXTRACTION ---
"""

def inject_metadata_code(original_code: str, image_filename: str, metadata_filename: str) -> str:
    """
    准备最终脚本：修改原始代码以保存 'd' 对象，并附加元数据提取逻辑。
    """
    # 确保 'd' 对象在 'with' 块之外也有效
    # 同时，我们将文件名直接写死，因为沙箱会在指定目录执行
    modified_code = original_code.replace(
        "with schemdraw.Drawing(",
        "d = schemdraw.Drawing("
    ).replace(
        "file='circuit_diagram.svg'",  # 假设AI生成的代码会使用这个标准文件名
        f"file='{image_filename}'"
    )
    
    # 如果AI没有生成 file=... 参数，我们手动添加
    if f"file='{image_filename}'" not in modified_code:
        modified_code = modified_code.replace(
            "schemdraw.Drawing(",
            f"schemdraw.Drawing(file='{image_filename}', "
        )

    metadata_code = generate_metadata_code(image_filename, metadata_filename)
    return modified_code + "\n\n" + metadata_code