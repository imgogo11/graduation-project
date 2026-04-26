import pandas as pd
import argparse
from pathlib import Path

# 定义所有必填的字段及其分类
REQUIRED_FIELDS = {
    "单股日线字段": [
        "stock_code", "stock_name", "trade_date", "open", "high", "low", 
        "close", "volume", "amount", "turnover_rate", "adjust_type", "data_source"
    ],
    "基准指数字段": [
        "benchmark_code", "benchmark_name", "benchmark_trade_date", "benchmark_close"
    ],
    "交易日历字段": [
        "calendar_trade_date"
    ],
    "估值字段": [
        "pe_ttm", "pb", "total_market_value", "circulating_market_value"
    ],
    "基本面字段": [
        "roe", "asset_liability_ratio", "revenue_yoy", "net_profit_yoy"
    ]
}

def check_file_fields(file_path):
    path = Path(file_path)
    if not path.exists():
        print(f"❌ 错误：文件 {file_path} 不存在。")
        return

    print(f"📄 正在检查文件: {path.name} ...")
    
    try:
        # 只读取表头，节约内存及提高速度
        if path.suffix.lower() == '.csv':
            df = pd.read_csv(file_path, nrows=0)
        elif path.suffix.lower() in ['.xlsx', '.xls']:
            df = pd.read_excel(file_path, nrows=0)
        else:
            print(f"❌ 错误：不支持的文件格式 {path.suffix}，仅支持 .csv 或 .xlsx/.xls。")
            return
    except Exception as e:
        print(f"❌ 读取文件出错: {e}")
        return

    actual_columns = set(df.columns)
    
    all_passed = True
    print("📊 字段检查结果：")
    for category, fields in REQUIRED_FIELDS.items():
        missing_fields = [f for f in fields if f not in actual_columns]
        if missing_fields:
            print(f"  ❌ [{category}] 缺失字段: {', '.join(missing_fields)}")
            all_passed = False
        else:
            print(f"  ✅ [{category}] 完整包含")

    print("-" * 40)
    if all_passed:
        print("🎉 结论: 该文件包含了所有要求的完整字段！")
    else:
        print("⚠️ 结论: 该文件缺失部分要求字段，请检查上方输出。")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="检查指定目录下所有数据文件是否包含要求字段")
    parser.add_argument("--dir", type=str, default=r"D:\graduation-project\data\row", help="要批量检查的目录路径")
    args = parser.parse_args()

    directory = Path(args.dir)
    
    if not directory.exists() or not directory.is_dir():
        print(f"❌ 错误：目录 {args.dir} 不存在或不是有效目录。")
        exit(1)

    print(f"🔍 开始检查目录: {directory} 及其中的数据文件...")
    
    # 获取所有的 csv, xlsx, xls 文件
    files_to_check = []
    files_to_check.extend(directory.glob("*.csv"))
    files_to_check.extend(directory.glob("*.xlsx"))
    files_to_check.extend(directory.glob("*.xls"))

    if not files_to_check:
        print("⚠️ 没有在该目录下找到任何 .csv 或 .xlsx/.xls 文件。")
    else:
        for file in files_to_check:
            print("\n" + "=" * 50)
            check_file_fields(str(file))
        
        print("\n" + "=" * 50)
        print("✅ 目录内所有文件已检查完毕！")