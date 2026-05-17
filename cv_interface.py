import os
import tempfile
import csv

def process_video(video_path: str) -> str:
    """
    Заглушка CV-модели. Создаёт CSV с правильными полями и одной тестовой строкой.
    """
    print(f"[CV] Обработка видео: {video_path}")

    # Поля, как в задании (31 колонка)
    columns = [
        'filename', 'product_name', 'price_default', 'price_card', 'price_discount',
        'barcode', 'discount_amount', 'id_sku', 'print_datetime', 'code',
        'additional_info', 'color', 'special_symbols', 'frame_timestamp',
        'x_min', 'y_min', 'x_max', 'y_max', 'qr_code_barcode', 'price1_qr',
        'price2_qr', 'price3_qr', 'price4_qr', 'wholesale_level_1_count',
        'wholesale_level_1_price', 'wholesale_level_2_count', 'wholesale_level_2_price',
        'action_price_qr', 'action_code_qr'
    ]

    # Создаём временный CSV файл
    temp_csv = tempfile.NamedTemporaryFile(delete=False, suffix='.csv', mode='w', newline='', encoding='utf-8-sig')
    writer = csv.writer(temp_csv)
    writer.writerow(columns)

    # Добавляем одну тестовую строку (пустую, только имя видео)
    row = [os.path.basename(video_path)] + [''] * (len(columns) - 1)
    writer.writerow(row)
    temp_csv.close()

    return temp_csv.name