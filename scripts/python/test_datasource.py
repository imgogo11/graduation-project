import argparse

import akshare as ak
import baostock as bs
import pandas as pd


GBJG_CHANGE_DATE = "\u53d8\u66f4\u65e5\u671f"
GBJG_TOTAL_SHARE = "\u603b\u80a1\u672c"
THS_REPORT_DATE = "\u62a5\u544a\u671f"
THS_REVENUE_YOY = "\u8425\u4e1a\u603b\u6536\u5165\u540c\u6bd4\u589e\u957f\u7387"
YJBB_NOTICE_DATE = "\u6700\u65b0\u516c\u544a\u65e5\u671f"
YJBB_ROE = "\u51c0\u8d44\u4ea7\u6536\u76ca\u7387"
YJBB_REVENUE_YOY = "\u8425\u4e1a\u603b\u6536\u5165-\u540c\u6bd4\u589e\u957f"
YJBB_NET_PROFIT_YOY = "\u51c0\u5229\u6da6-\u540c\u6bd4\u589e\u957f"
ZCFZ_NOTICE_DATE = "\u516c\u544a\u65e5\u671f"
ZCFZ_ASSET_LIABILITY_RATIO = "\u8d44\u4ea7\u8d1f\u503a\u7387"


def test_akshare() -> bool:
    print("Testing AkShare...")
    try:
        calendar_df = ak.tool_trade_date_hist_sina()
        benchmark_df = ak.stock_zh_index_daily(symbol="sh000300")
        daily_df = ak.stock_zh_a_daily(symbol="sz000001", start_date="20160101", end_date="20160115")
        share_change_df = ak.stock_zh_a_gbjg_em(symbol="000001.SZ")
        fundamentals_df = ak.stock_financial_abstract_ths(symbol="000001")
        yjbb_df = ak.stock_yjbb_em(date="20251231")
        zcfz_df = ak.stock_zcfz_em(date="20251231")

        print("AkShare calendar columns:")
        print(calendar_df.columns.tolist())
        print("AkShare benchmark columns:")
        print(benchmark_df.columns.tolist())
        print("AkShare daily columns:")
        print(daily_df.columns.tolist())
        print("AkShare share-change columns:")
        print(share_change_df.columns.tolist())
        print("AkShare financial abstract columns:")
        print(fundamentals_df.columns.tolist())
        print("AkShare market performance report columns:")
        print(yjbb_df.columns.tolist())
        print("AkShare market balance sheet columns:")
        print(zcfz_df.columns.tolist())

        required_daily_columns = {"date", "close", "outstanding_share"}
        if not required_daily_columns.issubset(set(daily_df.columns)):
            print(f"AkShare daily is missing columns: {sorted(required_daily_columns - set(daily_df.columns))}")
            return False

        required_share_change_columns = {GBJG_CHANGE_DATE, GBJG_TOTAL_SHARE}
        if not required_share_change_columns.issubset(set(share_change_df.columns)):
            print(
                "AkShare share-change is missing columns: "
                f"{sorted(required_share_change_columns - set(share_change_df.columns))}"
            )
            return False

        required_fundamental_columns = {THS_REPORT_DATE, THS_REVENUE_YOY}
        if not required_fundamental_columns.issubset(set(fundamentals_df.columns)):
            print(
                "AkShare financial abstract is missing columns: "
                f"{sorted(required_fundamental_columns - set(fundamentals_df.columns))}"
            )
            return False

        required_yjbb_columns = {YJBB_NOTICE_DATE, YJBB_ROE, YJBB_REVENUE_YOY, YJBB_NET_PROFIT_YOY}
        if not required_yjbb_columns.issubset(set(yjbb_df.columns)):
            print(
                "AkShare market performance report is missing columns: "
                f"{sorted(required_yjbb_columns - set(yjbb_df.columns))}"
            )
            return False

        required_zcfz_columns = {ZCFZ_NOTICE_DATE, ZCFZ_ASSET_LIABILITY_RATIO}
        if not required_zcfz_columns.issubset(set(zcfz_df.columns)):
            print(
                "AkShare market balance sheet is missing columns: "
                f"{sorted(required_zcfz_columns - set(zcfz_df.columns))}"
            )
            return False

        print("AkShare sample data fetched successfully.")
        return True
    except Exception as exc:
        print(f"AkShare failed: {exc}")
        return False


def fetch_bs_frame(result_set) -> pd.DataFrame:
    if result_set.error_code != "0":
        raise RuntimeError(f"{result_set.error_code} {result_set.error_msg}")
    rows = []
    while result_set.error_code == "0" and result_set.next():
        rows.append(result_set.get_row_data())
    return pd.DataFrame(rows, columns=result_set.fields)


def test_baostock(include_quarterly: bool = False) -> bool:
    print("Testing BaoStock...")
    login_result = bs.login()
    if login_result.error_code != "0":
        print(f"BaoStock login failed: {login_result.error_code} {login_result.error_msg}")
        return False

    try:
        daily_df = fetch_bs_frame(
            bs.query_history_k_data_plus(
                "sz.000001",
                "date,code,open,high,low,close,preclose,volume,amount,adjustflag,turn,tradestatus,pctChg,peTTM,pbMRQ,psTTM,pcfNcfTTM",
                start_date="2023-01-01",
                end_date="2023-01-10",
                frequency="d",
                adjustflag="3",
            )
        )

        print("BaoStock daily columns:")
        print(daily_df.columns.tolist())

        if daily_df.empty:
            print("BaoStock returned an empty dataframe.")
            return False

        if include_quarterly:
            profit_df = fetch_bs_frame(bs.query_profit_data(code="sz.000001", year=2025, quarter=4))
            growth_df = fetch_bs_frame(bs.query_growth_data(code="sz.000001", year=2025, quarter=4))
            balance_df = fetch_bs_frame(bs.query_balance_data(code="sz.000001", year=2025, quarter=4))

            print("BaoStock profit columns:")
            print(profit_df.columns.tolist())
            print("BaoStock growth columns:")
            print(growth_df.columns.tolist())
            print("BaoStock balance columns:")
            print(balance_df.columns.tolist())

            if profit_df.empty or growth_df.empty or balance_df.empty:
                print("BaoStock quarterly endpoint returned an empty dataframe.")
                return False

        print("BaoStock sample data fetched successfully.")
        return True
    except Exception as exc:
        print(f"BaoStock failed: {exc}")
        return False
    finally:
        bs.logout()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Smoke-test AkShare and BaoStock datasource availability")
    parser.add_argument(
        "--include-baostock-quarterly",
        action="store_true",
        help="Also test BaoStock quarterly financial endpoints; not needed by the default batch fetch mode",
    )
    args = parser.parse_args()

    ak_ok = test_akshare()
    bs_ok = test_baostock(include_quarterly=args.include_baostock_quarterly)
    raise SystemExit(0 if ak_ok and bs_ok else 1)
