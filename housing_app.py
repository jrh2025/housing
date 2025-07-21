import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
from fpdf import FPDF
from fpdf.enums import XPos, YPos
import os
import re
from datetime import datetime

# --- 基礎設定：中文字體與數字格式化 ---

# 1. 字體設定 (*** REVISED LOGIC FOR CLOUD DEPLOYMENT ***)
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import os
import streamlit as st

# ---
# 這是確保 Streamlit Cloud 部署成功的關鍵程式碼
# ---
font_path = 'NotoSansTC-Regular.ttf'

# 檢查字體檔是否存在於儲存庫中
if os.path.exists(font_path):
    # 如果存在，則將其加入 Matplotlib 的字體管理器
    fm.fontManager.addfont(font_path)
    
    # 設定 Matplotlib 的預設字體為我們剛剛載入的字體
    # 我們從字體檔案中獲取字體的名稱
    font_prop = fm.FontProperties(fname=font_path)
    plt.rcParams['font.family'] = font_prop.get_name()
    
    # 解決負號顯示問題
    plt.rcParams['axes.unicode_minus'] = False
    
    # 在日誌中打印成功訊息，方便除錯
    print(f"Font '{font_prop.get_name()}' found and set as default for matplotlib.")

else:
    # 如果在雲端找不到字體檔，這將是一個嚴重的錯誤
    st.error(f"字體檔 '{font_path}' 不存在，請確認已將其上傳至 GitHub 儲存庫的根目錄。")
    print(f"CRITICAL ERROR: Font file '{font_path}' not found in the repository.")

# 2. 數字格式化函式
def format_large_number(num, precision=0):
    """將大數字格式化為易於閱讀的中文單位 (億、萬)，低於十萬則顯示完整金額。"""
    if not isinstance(num, (int, float)):
        return "N/A"
    if abs(num) >= 1_0000_0000:
        return f"{num / 1_0000_0000:,.{precision}f} 億"
    if abs(num) >= 10_0000:
        return f"{num / 1_0000:,.{precision}f} 萬"
    return f"{num:,.0f}"

# --- 核心模擬與計算函式 ---

def calculate_pmt(loan_amount, monthly_rate, num_payments):
    """計算每月房貸還款額（本息平均攤還）"""
    if monthly_rate > 0:
        return loan_amount * (monthly_rate * (1 + monthly_rate)**num_payments) / ((1 + monthly_rate)**num_payments - 1)
    if num_payments > 0:
        return loan_amount / num_payments
    return 0

def simulate_down_payment(params):
    """第一階段：頭期款準備期模擬"""
    all_trajectories = []
    months_limit = params['prep_years_limit'] * 12
    target_down_payment = params['target_house_price'] * params['down_payment_ratio']
    monthly_return_mean = (1 + params['annual_return_mean']) ** (1/12) - 1
    monthly_return_std = params['annual_return_std'] / np.sqrt(12)
    
    success_count = 0
    total_months_to_goal = []

    for _ in range(params['simulations']):
        current_savings = params['initial_savings']
        trajectory = [current_savings]
        
        for month in range(1, months_limit + 1):
            current_savings += params['monthly_savings']
            monthly_return = np.random.normal(monthly_return_mean, monthly_return_std)
            current_savings *= (1 + monthly_return)
            trajectory.append(current_savings)
            
            if current_savings >= target_down_payment:
                success_count += 1
                total_months_to_goal.append(month)
                break
        
        all_trajectories.append(trajectory)

    success_rate = success_count / params['simulations']
    average_years_to_goal = (np.mean(total_months_to_goal) / 12) if total_months_to_goal else None
    
    return {
        "success_rate": success_rate,
        "average_years": average_years_to_goal,
        "all_trajectories": all_trajectories,
        "target_down_payment": target_down_payment
    }

def simulate_mortgage_period(params):
    """第二階段：房貸與持有期模擬 (強化版)"""
    house_price = params['target_house_price']
    down_payment_amount = house_price * params['down_payment_ratio']
    loan_amount = house_price - down_payment_amount
    
    monthly_mortgage_rate = params['mortgage_rate'] / 12
    num_mortgage_payments = params['mortgage_years'] * 12
    pmt = calculate_pmt(loan_amount, monthly_mortgage_rate, num_mortgage_payments)

    monthly_holding_cost = (house_price * params['annual_holding_cost_ratio']) / 12
    
    monthly_investment_return_mean = (1 + params['post_purchase_return_mean']) ** (1/12) - 1
    monthly_investment_return_std = params['post_purchase_return_std'] / np.sqrt(12)
    
    all_net_worth_trajectories = []
    asset_depletion_count = 0
    final_net_worths = []
    final_financial_assets = []

    for _ in range(params['simulations']):
        financial_assets = 0 
        current_house_value = house_price
        remaining_loan = loan_amount
        net_worth_trajectory = [current_house_value - remaining_loan]
        is_depleted = False

        for month in range(1, num_mortgage_payments + 1):
            if is_depleted:
                net_worth_trajectory.append(net_worth_trajectory[-1])
                continue

            disposable_income = params['monthly_income'] - params['monthly_expenses'] - pmt - monthly_holding_cost
            financial_assets += disposable_income
            monthly_return = np.random.normal(monthly_investment_return_mean, monthly_investment_return_std)
            financial_assets *= (1 + monthly_return)
            
            interest_paid = remaining_loan * monthly_mortgage_rate
            principal_paid = pmt - interest_paid
            remaining_loan -= principal_paid

            current_net_worth = financial_assets + current_house_value - max(0, remaining_loan)
            net_worth_trajectory.append(current_net_worth)

            if financial_assets < 0:
                asset_depletion_count += 1
                is_depleted = True
        
        if not is_depleted:
            final_net_worths.append(net_worth_trajectory[-1])
            final_financial_assets.append(financial_assets)
        
        all_net_worth_trajectories.append(net_worth_trajectory)

    return {
        "monthly_mortgage_payment": pmt,
        "monthly_holding_cost": monthly_holding_cost,
        "asset_depletion_risk": asset_depletion_count / params['simulations'],
        "all_net_worth_trajectories": all_net_worth_trajectories,
        "final_net_worths": final_net_worths,
        "final_financial_assets": final_financial_assets,
        "loan_amount": loan_amount
    }


# --- 圖表產生函式 ---

def plot_stress_index_gauge(index_value):
    fig, ax = plt.subplots(figsize=(8, 1.5))
    zones = {'舒適區': (0, 0.3, '#2ca02c'), '觀察區': (0.3, 0.4, '#ff7f0e'), '警戒區': (0.4, 0.6, '#d62728')}
    for name, (start, end, color) in zones.items():
        ax.axvspan(start, end, color=color, alpha=0.6)
        ax.text((start + end) / 2, 0.5, f'{name}\n({start*100:.0f}%-{end*100:.0f}%)', 
                ha='center', va='center', fontsize=12, color='white', weight='bold')
    if index_value <= 0.6:
        ax.arrow(index_value, 0.8, 0, -0.4, head_width=0.015, head_length=0.1, fc='black', ec='black', lw=2)
        ax.text(index_value, 0.9, f'您在 {index_value:.1%}', ha='center', va='bottom', fontsize=14, weight='bold')
    else:
        ax.arrow(0.58, 0.8, 0, -0.4, head_width=0.015, head_length=0.1, fc='black', ec='black', lw=2)
        ax.text(0.58, 0.9, f'您在 {index_value:.1%} (已超標)', ha='center', va='bottom', fontsize=14, weight='bold')
    ax.set_xlim(0, 0.6); ax.set_ylim(0, 1)
    ax.set_xticks([]); ax.set_yticks([])
    for spine in ax.spines.values(): spine.set_visible(False)
    fig.tight_layout()
    return fig

def plot_cash_flow_pie(data, labels, monthly_income):
    fig, ax = plt.subplots(figsize=(6, 6))
    colors = ['#d62728', '#ff7f0e', '#1f77b4', '#2ca02c'] 
    
    if sum(data) > monthly_income:
        data[3] = 0
    
    wedges, texts, autotexts = ax.pie(data, labels=None, autopct='%1.1f%%', startangle=90,
                                      colors=colors, pctdistance=0.85,
                                      wedgeprops=dict(width=0.4, edgecolor='w'))
    
    ax.text(0, 0, f'月總收入\n{format_large_number(monthly_income)}元',
            ha='center', va='center', fontsize=20, weight='bold')
    
    plt.setp(autotexts, size=12, weight="bold", color="white")
    
    legend_labels = [f'{l}: {format_large_number(v)}元' for l, v in zip(labels, data)]
    ax.legend(wedges, legend_labels, title="每月現金流向", loc="center left", bbox_to_anchor=(1, 0, 0.5, 1), fontsize=12)
    
    ax.axis('equal')
    return fig

def plot_cost_benefit_analysis(costs, benefits):
    fig, ax = plt.subplots(figsize=(10, 6))
    
    categories = ['真實購屋總成本', '最終總淨資產 (中位數)']
    values = [sum(costs.values()), sum(benefits.values())]
    
    bars = ax.bar(categories, values, color=['#d62728', '#2ca02c'])
    
    for bar in bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width() / 2.0, height, format_large_number(height),
                ha='center', va='bottom', fontsize=14, weight='bold')
    
    cost_bottom = 0
    cost_labels = ['房屋本金', '總利息', '總持有成本']
    cost_colors = ['#ff9896', '#c5b0d5', '#c49c94']
    for i, (label, value) in enumerate(costs.items()):
        ax.bar(categories[0], value, bottom=cost_bottom, label=f'{cost_labels[i]}: {format_large_number(value)}', color=cost_colors[i])
        cost_bottom += value

    benefit_bottom = 0
    benefit_labels = ['房屋價值', '累積金融資產']
    benefit_colors = ['#a1d99b', '#9ecae1']
    for i, (label, value) in enumerate(benefits.items()):
        ax.bar(categories[1], value, bottom=benefit_bottom, label=f'{benefit_labels[i]}: {format_large_number(value)}', color=benefit_colors[i])
        benefit_bottom += value

    ax.set_ylabel('金額 (元)', fontsize=12)
    ax.set_title('購屋長期成本效益分析', fontsize=16, pad=20)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: format_large_number(x)))
    ax.legend(title="細項分析", loc='upper left')
    ax.grid(axis='y', linestyle='--', alpha=0.7)
    
    return fig

def plot_accumulation_chart(trajectories, target, years_limit, title):
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.set_title(title, fontsize=16, pad=20)
    ax.set_xlabel('準備年期 (年)', fontsize=12)
    ax.set_ylabel('累積資產 (萬元)', fontsize=12)
    for trajectory in trajectories[:100]:
        years_axis = np.arange(len(trajectory)) / 12
        ax.plot(years_axis, np.array(trajectory) / 10000, color='gray', alpha=0.2)
    max_len = max(len(t) for t in trajectories) if trajectories else 0
    padded_trajectories = [t + [np.nan] * (max_len - len(t)) for t in trajectories]
    median_trajectory = np.nanmedian(padded_trajectories, axis=0)
    years_axis_median = np.arange(len(median_trajectory)) / 12
    ax.plot(years_axis_median, median_trajectory / 10000, color='blue', linewidth=2.5, label='資產中位數')
    ax.axhline(y=target / 10000, color='green', linestyle='--', label=f'目標金額: {format_large_number(target)}')
    ax.set_xlim(0, years_limit)
    ax.grid(True, linestyle='--', alpha=0.6)
    ax.legend(fontsize=10)
    fig.tight_layout()
    return fig

def plot_net_worth_chart(trajectories, years, title):
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.set_title(title, fontsize=16, pad=20)
    ax.set_xlabel('持有年期 (年)', fontsize=12)
    ax.set_ylabel('總淨資產 (萬元)', fontsize=12)
    for trajectory in trajectories[:100]:
        years_axis = np.arange(len(trajectory)) / 12
        ax.plot(years_axis, np.array(trajectory) / 10000, color='gray', alpha=0.2)
    max_len = max(len(t) for t in trajectories) if trajectories else 0
    padded_trajectories = [t + [np.nan] * (max_len - len(t)) for t in trajectories]
    median_trajectory = np.nanmedian(padded_trajectories, axis=0)
    years_axis_median = np.arange(len(median_trajectory)) / 12
    ax.plot(years_axis_median, median_trajectory / 10000, color='red', linewidth=2.5, label='淨資產中位數')
    ax.set_xlim(0, years)
    ax.grid(True, linestyle='--', alpha=0.6)
    ax.legend(fontsize=10)
    fig.tight_layout()
    return fig

# --- PDF 產生函式 ---
class PDF(FPDF):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        font_path = 'NotoSansTC-Regular.ttf'
        if os.path.exists(font_path):
            self.add_font('NotoSans', '', font_path)
        else:
            st.warning("未找到 'NotoSansTC-Regular.ttf' 字體檔，PDF 中的中文可能無法顯示。")
            self.add_font('NotoSans', '', 'helvetica.ttf') 

    def header(self):
        self.set_font('NotoSans', '', 16)
        self.cell(0, 10, '青年購屋財務規劃模擬報告', new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='C')
        self.set_font('NotoSans', '', 8)
        self.cell(0, 5, f'報告生成時間: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}', new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='C')
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font('NotoSans', '', 8)
        self.cell(0, 10, f'第 {self.page_no()} 頁', align='C')

    def chapter_title(self, title):
        self.set_font('NotoSans', '', 14)
        self.set_fill_color(220, 220, 220)
        self.cell(0, 10, title, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='L', fill=True)
        self.ln(5)

    def chapter_body(self, content):
        self.set_font('NotoSans', '', 10)
        self.multi_cell(0, 7, content)
        self.ln()

# (*** REVISED LOGIC - ROBUST PDF LAYOUT ***)
def create_pdf_report(params, texts, figs):
    """使用穩健的自動佈局生成PDF，確保所有內容完整呈現"""
    pdf = PDF()
    
    # 第1頁: 總結與第一階段分析
    pdf.add_page()
    pdf.chapter_title('一、總體財務評估')
    pdf.chapter_body(texts['narrative_summary'])
    pdf.chapter_body(texts['summary_p1'] + "\n" + texts['summary_p2'])
    if os.path.exists(figs['stress_gauge_path']):
        pdf.image(figs['stress_gauge_path'], x=10, y=None, w=190)
    pdf.ln(5)

    pdf.chapter_title('二、頭期款準備分析')
    pdf.chapter_body(texts['phase1_analysis'])
    if os.path.exists(figs['phase1_chart_path']):
        pdf.image(figs['phase1_chart_path'], x=10, y=None, w=190)
    
    # 第2頁: 第二階段分析的詳細文本
    pdf.add_page()
    pdf.chapter_title('三、房貸與持有期分析 (詳細報告)')
    pdf.chapter_body(texts['phase2_analysis'])

    # 第3頁: 第二階段分析的圖表
    pdf.add_page()
    pdf.chapter_title('三、房貸與持有期分析 (圖表)')
    if os.path.exists(figs['cash_flow_pie_path']):
        pdf.chapter_body("每月現金流向分佈：")
        pdf.image(figs['cash_flow_pie_path'], x=pdf.get_x(), y=None, w=180)
        pdf.ln(5)
    if os.path.exists(figs['cost_benefit_path']):
        pdf.chapter_body("長期成本效益分析：")
        pdf.image(figs['cost_benefit_path'], x=10, y=None, w=190)
        pdf.ln(5)
    if os.path.exists(figs['phase2_chart_path']):
        pdf.chapter_body("淨資產成長軌跡：")
        pdf.image(figs['phase2_chart_path'], x=10, y=None, w=190)

    # 第4頁: 參數與聲明
    pdf.add_page()
    pdf.chapter_title('四、本次模擬參數回顧')
    pdf.chapter_body(texts['params'])
    pdf.chapter_title('五、名詞解釋與免責聲明')
    pdf.chapter_body(texts['disclaimer'])
    
    return bytes(pdf.output())

# --- 輔助函式 ---
def generate_narrative_summary(p):
    """產生口語化的報告前提摘要"""
    return (
        f"這份報告是為您量身打造的購屋財務模擬。我們假設您的目標是購買一間總價 **{format_large_number(p['target_house_price'])}** 元的房子，"
        f"並計畫準備 **{p['down_payment_ratio']:.0%}**（約 **{format_large_number(p['target_house_price'] * p['down_payment_ratio'])}** 元）的頭期款。"
        f"您目前已有 **{format_large_number(p['initial_savings'])}** 元的儲蓄，並打算每月再投入 **{p['monthly_savings']:,}** 元，"
        f"希望在 **{p['prep_years_limit']}** 年內達成目標。\n\n"
        f"購屋後，我們假設您的家庭月收入為 **{format_large_number(p['monthly_income'])}** 元，"
        f"並將以 **{p['mortgage_rate']:.2%}** 的利率，背負一筆為期 **{p['mortgage_years']}** 年的房貸。"
        f"以下分析將基於這些前提，為您剖析此財務決策的可行性與長期影響。"
    )

def handle_suggestion_click(param_updates):
    """處理建議方案按鈕點擊的通用函式，並直接觸發模擬"""
    st.session_state.params.update(param_updates)
    st.session_state.run_simulation = True
    st.rerun()

def strip_markdown_for_pdf(text):
    """移除簡單的 Markdown 和 HTML 標籤，用於 PDF 純文字輸出"""
    text = re.sub(r'^[#]+\s*', '', text, flags=re.MULTILINE) 
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text) 
    text = re.sub(r'__(.*?)__', r'\1', text) 
    text = re.sub(r'\*(.*?)\*', r'\1', text) 
    text = re.sub(r'_(.*?)_', r'\1', text) 
    text = re.sub(r'^\s*-\s', '', text, flags=re.MULTILINE) 
    text = re.sub(r'<[^>]+>', '', text) 
    return text.strip()

# --- Streamlit App 主體 ---
st.set_page_config(page_title="青年購屋財務規劃模擬器 v4.0", layout="wide")

page = st.sidebar.radio("導覽", ["🏠 購屋財務模擬器", "📖 設計理念與使用說明"])

if page == "📖 設計理念與使用說明":
    st.title("📖 設計理念與使用說明")
    st.header("設計哲學：您的個人化財務飛行模擬器")
    st.markdown("""
    傳統的房貸計算機只能給您一個基於固定假設的單一答案，但真實世界充滿了不確定性。購屋是一項長達20至40年的重大財務承諾，期間必然會經歷市場的多空循環、個人收入的成長與停滯、以及非預期的開銷。
    本工具的核心理念是**拒絕提供虛幻的確定性，轉而擁抱機率性的未來**。我們將其打造成一個專屬於您的「財務飛行模擬器」，讓您能在實際投入巨額資金前，先在數千種可能的未來情境中進行壓力測試，從而做出更穩健、更明智的決策。
    我們的設計基石包含：
    - **擁抱不確定性**：透過「蒙地卡羅模擬」，我們模擬數千次您未來可能的財務路徑。最終呈現的不是一個絕對的數字，而是計畫的「成功機率」，讓您對風險有更直觀的理解。
    - **量化財務壓力**：我們不只關心「您買不買得起」，更關心「您買了之後過得好不好」。透過「財務壓力指數」等關鍵指標，我們量化了購屋決策對您日常現金流的影響。
    - **洞察權衡取捨**：購屋決策充滿了各種權衡。想降低月付金，可能要拉長年期或降低總價；想提高頭期款達標率，可能需要增加儲蓄或延長準備期。本工具讓您能透過互動調整，直觀地看見不同決策之間的利弊得失。
    """)
    st.header("如何有效使用本工具？")
    st.markdown("""
    **第一步：誠實地設定您的財務現況與目標**
    在左側的「參數設定」區，請盡可能準確地輸入您的資料。
    - **第一階段 (頭期款準備期)**：這部分關注您如何在一定時間內存到頭期款。
        - `目前購屋儲蓄`：您已累積的本金。
        - `每月預計投入儲蓄`：您每月能穩定投入的金額。
        - `最長準備年期`：您給自己的時間底線。
        - `市場假設`：您對這段期間投資報酬率的預期。保守的投資人應選擇較低的報酬率與波動率。
    - **第二階段 (房貸與持有期)**：這部分關注您買房後的長期財務健康。
        - `每月稅後總收入`：這是計算財務壓力的基礎，請務必準確填寫。
        - `每月固定生活支出`：**不包含房貸**的所有開銷。一個常見的錯誤是低估此項。
    - **共同參數**：
        - `目標房屋總價`、`頭期款比例`、`房貸年期` 是您購屋計畫的核心。
        - `房貸利率`、`房屋年持有成本比例` 是影響您長期支出的關鍵。
    **第二步：執行模擬並解讀結果**
    點擊「執行模擬分析」後，請依序查看右側的三個分頁：
    1.  **📊 總結與建議**：
        - **優先查看！** 這裡提供了對您計畫兩個階段的總體評估（穩健、存在挑戰、壓力過高等）。
        - **財務壓力儀表板**會直觀地顯示您購屋後的現金流健康狀況。
        - 如果計畫存在弱點，下方會出現**針對性的優化建議**，您可以直接點擊「採納」來調整參數。
    2.  **📈 頭期款準備分析**：
        - 這裡詳細展示了您在期限內存到頭期款的**成功機率**。
        - 「財富累積軌跡圖」中的藍色中位數線，代表了50%的模擬結果會高於此線，50%則低於此線，是您最可能的財富路徑參考。
    3.  **📉 房貸與持有期分析**：
        - **每月現金流儀表板**詳細拆解了您買房後的收支結構，讓您清楚知道錢花在哪，以及每月還能剩下多少錢可以再投資。
        - **購屋總成本及淨值效益分析**則計算了您在整個房貸期間的總支出，以及最終可能累積的資產。這是評估「房子究竟是資產還是負債」的關鍵數據。
    **第三步：反覆測試與優化**
    財務規劃是一個動態調整的過程。請不要只滿足於一次的模擬結果。嘗試調整不同的參數組合，例如：
    - 「如果我多準備兩年，成功率會提高多少？」
    - 「如果房價再高100萬，我的財務壓力會到哪個等級？」
    - 「如果我每月能多存5000元，最終的淨資產會差多少？」
    透過這些反覆的模擬，您將能找到最適合自己的、風險可控的購屋路徑。
    """)
    st.stop()

st.title("🏠 青年購屋財務規劃模擬器 v4.0")

# --- 初始化 Session State ---
if 'params' not in st.session_state:
    st.session_state.params = {
        'initial_savings': 800000, 'monthly_savings': 30000, 'monthly_income': 85000,
        'monthly_expenses': 25000, 'target_house_price': 15000000, 'down_payment_ratio': 0.20,
        'prep_years_limit': 10, 'mortgage_years': 30, 'annual_return_mean': 0.08,
        'annual_return_std': 0.16, 'mortgage_rate': 0.022, 'annual_holding_cost_ratio': 0.006,
        'post_purchase_return_mean': 0.06, 'post_purchase_return_std': 0.14, 'simulations': 2000
    }

# --- 複合式輸入元件函式 ---
def create_slider_input(label, min_val, max_val, key_prefix, unit, help_text, format_str, step):
    c1, c2 = st.columns([0.7, 0.3])
    current_value_percent = st.session_state.params[key_prefix] * 100
    slider_val = c1.slider(label, min_val, max_val, current_value_percent, help=help_text, key=f'slider_{key_prefix}')
    number_val = c2.number_input(unit, min_val, max_val, current_value_percent, label_visibility="collapsed", key=f'num_{key_prefix}', format=format_str, step=step)
    if slider_val != current_value_percent:
        st.session_state.params[key_prefix] = slider_val / 100
        st.rerun()
    elif number_val != current_value_percent:
        st.session_state.params[key_prefix] = number_val / 100
        st.rerun()

# --- 側邊欄參數設定 ---
with st.sidebar:
    st.header("⚙️ 參數設定")
    st.info("大部分滑桿旁都有數字輸入框，方便精確調整。")
    with st.expander("第一階段：頭期款準備期", expanded=True):
        st.subheader("個人財務")
        st.session_state.params['initial_savings'] = st.number_input("目前購屋儲蓄", min_value=0, value=st.session_state.params['initial_savings'], step=50000, format="%d", help="您目前已經為購屋準備的存款或投資資產總額。")
        st.session_state.params['monthly_savings'] = st.number_input("每月預計投入儲蓄", min_value=0, value=st.session_state.params['monthly_savings'], step=1000, format="%d", help="每月預計能為購屋目標投入的儲蓄金額。建議：應在不影響生活品質下，盡量提高。")
        st.subheader("準備期目標")
        st.session_state.params['prep_years_limit'] = st.slider("最長準備年期 (年)", 1, 20, st.session_state.params['prep_years_limit'], 1, help="您給自己準備頭期款的最長期限。建議：可依據您的年齡與生涯規劃設定。")
        st.subheader("市場假設 (準備期)")
        create_slider_input("年化平均報酬率", 1.0, 15.0, 'annual_return_mean', "%", "儲蓄期間，您投資組合的長期年化『平均』報酬率預期。\n\n參考：全球股市長期約8%-10%，債券約2%-4%，可依您的股債配置比例估算。", "%.1f", 0.5)
        create_slider_input("年化報酬波動率", 5.0, 30.0, 'annual_return_std', "% ", "報酬率的波動程度(風險)。\n\n參考：全球股市約15%-20%。波動率越高，達標時間的不確定性越大。", "%.1f", 0.5)
    with st.expander("第二階段：房貸與持有期", expanded=True):
        st.subheader("個人財務")
        st.session_state.params['monthly_income'] = st.number_input("每月稅後總收入", min_value=0, value=st.session_state.params['monthly_income'], step=5000, format="%d", help="購屋後，您個人或家庭的每月稅後總收入。這是計算財務壓力的關鍵。")
        st.session_state.params['monthly_expenses'] = st.number_input("每月固定生活支出", min_value=0, value=st.session_state.params['monthly_expenses'], step=1000, format="%d", help="扣除『房貸』與『房屋持有成本』外的所有每月生活開銷，例如伙食、交通、娛樂、保險等。建議：可估算為稅後收入的30%-40%。")
        st.subheader("市場假設 (持有期)")
        create_slider_input("年化平均報酬率 (持有期)", 1.0, 15.0, 'post_purchase_return_mean', "%", "購屋後，您剩餘金融資產(如有)的投資組合長期年化報酬率預期。", "%.1f", 0.5)
        create_slider_input("年化報酬波動率 (持有期)", 5.0, 30.0, 'post_purchase_return_std', "% ", "購屋後，剩餘金融資產的報酬波動率。", "%.1f", 0.5)
    with st.expander("共同參數", expanded=True):
        st.subheader("購屋目標")
        st.session_state.params['target_house_price'] = st.number_input("目標房屋總價", min_value=0, value=st.session_state.params['target_house_price'], step=100000, format="%d", help="您預計購買的房屋總價。")
        create_slider_input("預計頭期款比例", 10.0, 50.0, 'down_payment_ratio', "%", "頭期款佔房屋總價的比例。\n\n建議：台灣普遍為20%-30%，若能提高，可有效降低總貸金額與月付金。", "%.1f", 1.0)
        st.caption(f"↳ 頭期款金額： **{format_large_number(st.session_state.params['target_house_price'] * st.session_state.params['down_payment_ratio'])}** 元")
        st.session_state.params['mortgage_years'] = st.select_slider("房貸年期 (年)", options=[20, 30, 40], value=st.session_state.params['mortgage_years'], help="常見房貸年期。年期越長，月付金越低，但總利息支出越高。")
        st.subheader("貸款與持有成本")
        create_slider_input("房貸利率", 1.0, 5.0, 'mortgage_rate', "%", "預估的房貸利率。\n\n參考：可參考近期銀行牌告利率或政府優惠貸款利率(如新青安，2024年約2.2%)。", "%.2f", 0.05)
        create_slider_input("房屋年持有成本比例", 0.1, 2.0, 'annual_holding_cost_ratio', "% ", "預估每年花在房屋上的成本佔房價的比例，包含房屋稅、地價稅、管理費、保險、預期修繕費等。\n\n建議：一般估算為房價的0.5%-1.0%。", "%.2f", 0.05)
        st.caption(f"↳ 預估年持有成本： **{format_large_number(st.session_state.params['target_house_price'] * st.session_state.params['annual_holding_cost_ratio'])}** 元")
    st.subheader("模擬設定")
    st.session_state.params['simulations'] = st.select_slider("模擬次數", options=[1000, 2000, 5000, 10000], value=st.session_state.params['simulations'], help="次數越多結果越穩定，但計算較久。")
    if st.button("🚀 執行模擬分析", type="primary", use_container_width=True):
        st.session_state.run_simulation = True
        st.session_state.suggestion_adopted = False # 清除建議提示

# --- 主畫面顯示 ---

if st.session_state.get('run_simulation', False):
    with st.spinner('🤖 正在為您執行蒙地卡羅模擬...請稍候...'):
        phase1_results = simulate_down_payment(st.session_state.params)
        phase2_results = simulate_mortgage_period(st.session_state.params)
        st.session_state.simulation_results = {'phase1': phase1_results, 'phase2': phase2_results}
    st.success('模擬完成！')
    st.session_state.run_simulation = False

if 'simulation_results' in st.session_state:
    params = st.session_state.params
    p1_res = st.session_state.simulation_results['phase1']
    p2_res = st.session_state.simulation_results['phase2']
    financial_stress_index = (p2_res['monthly_mortgage_payment'] + p2_res['monthly_holding_cost']) / params['monthly_income'] if params['monthly_income'] > 0 else 0

    tab1, tab2, tab3 = st.tabs(["📊 總結與建議", "📈 頭期款準備分析", "📉 房貸與持有期分析"])

    with tab1:
        st.header("總體財務評估")
        
        with st.container(border=True):
            st.markdown("##### **報告前提摘要**")
            narrative_summary = generate_narrative_summary(params)
            st.markdown(narrative_summary)

        p1_success = p1_res['success_rate'] >= 0.8
        p2_success = financial_stress_index <= 0.4

        with st.container(border=True):
            st.subheader("第一階段：頭期款準備期評估")
            if p1_success:
                st.success("✅ 計畫穩健")
                p1_summary = f"您的頭期款準備計畫相當穩健。根據模擬，在 **{params['prep_years_limit']}** 年的期限內，有高達 **{p1_res['success_rate']:.1%}** 的機率能成功存到 **{format_large_number(p1_res['target_down_payment'])}** 的目標。"
            else:
                st.warning("⚠️ 存在挑戰")
                p1_summary = f"您的頭期款準備計畫存在挑戰。在 **{params['prep_years_limit']}** 年的期限內，成功達標的機率僅 **{p1_res['success_rate']:.1%}**，可能需要比預期更長的時間或更積極的儲蓄策略。"
            st.markdown(p1_summary)

        with st.container(border=True):
            st.subheader("第二階段：房貸與持有期評估")
            if p2_success:
                st.success("✅ 財務健康")
                p2_summary = f"購屋後，您的財務狀況預期將保持健康。財務壓力指數為 **{financial_stress_index:.1%}**，位於「{ '舒適區' if financial_stress_index <= 0.3 else '觀察區'}」，顯示您有足夠的餘裕應對生活開銷與未來的不確定性。"
            else:
                st.error("🚨 壓力過高")
                p2_summary = f"購屋後，您的財務壓力可能過高。壓力指數達到 **{financial_stress_index:.1%}**，已進入「警戒區」，這可能嚴重影響您的生活品質，並降低應對突發狀況的能力。"
            st.markdown(p2_summary)
            stress_gauge_fig = plot_stress_index_gauge(financial_stress_index)
            st.pyplot(stress_gauge_fig)

        if not p1_success or not p2_success:
            st.write("---")
            st.subheader("🎯 智慧優化方案建議")
            st.info("以下針對您計畫的弱點提供調整建議。點擊「採納」即可更新參數並**立即重新模擬**。")
            
            cols = st.columns(3)
            col_idx = 0

            if not p1_success:
                with cols[col_idx % 3]:
                    with st.container(border=True, height=200):
                        st.markdown("###### **方案A: 提高月儲蓄**")
                        new_savings = int(params['monthly_savings'] * 1.15)
                        st.markdown(f"提高15%至 **{new_savings:,}** 元/月。")
                        st.markdown(f"<p style='color:green;'>➔ 提高達標率</p>", unsafe_allow_html=True)
                        if st.button("採納 A", key="optA", use_container_width=True): handle_suggestion_click({'monthly_savings': new_savings})
                col_idx += 1
                with cols[col_idx % 3]:
                    with st.container(border=True, height=200):
                        st.markdown("###### **方案B: 延長準備期**")
                        new_prep_years = params['prep_years_limit'] + 2
                        st.markdown(f"延長2年至 **{new_prep_years}** 年。")
                        st.markdown(f"<p style='color:green;'>➔ 爭取複利時間</p>", unsafe_allow_html=True)
                        if st.button("採納 B", key="optB", use_container_width=True): handle_suggestion_click({'prep_years_limit': new_prep_years})
                col_idx += 1
            
            if not p2_success:
                with cols[col_idx % 3]:
                    with st.container(border=True, height=200):
                        st.markdown("###### **方案C: 降低購屋總價**")
                        new_price = int(params['target_house_price'] * 0.9)
                        new_loan = new_price * (1 - params['down_payment_ratio']); new_pmt = calculate_pmt(new_loan, params['mortgage_rate']/12, params['mortgage_years']*12)
                        new_holding_cost = (new_price * params['annual_holding_cost_ratio']) / 12; new_stress_index = (new_pmt + new_holding_cost) / params['monthly_income'] if params['monthly_income'] > 0 else 0
                        st.markdown(f"降低10%至 **{format_large_number(new_price)}**。")
                        st.markdown(f"<p style='color:green;'>➔ 壓力指數降至 <b>{new_stress_index:.1%}</b></p>", unsafe_allow_html=True)
                        if st.button("採納 C", key="optC", use_container_width=True): handle_suggestion_click({'target_house_price': new_price})
                col_idx += 1
                with cols[col_idx % 3]:
                    with st.container(border=True, height=200):
                        st.markdown("###### **方案D: 提高頭期款**")
                        new_dp_ratio = params['down_payment_ratio'] + 0.05
                        new_loan = params['target_house_price'] * (1 - new_dp_ratio); new_pmt = calculate_pmt(new_loan, params['mortgage_rate']/12, params['mortgage_years']*12)
                        new_holding_cost = (params['target_house_price'] * params['annual_holding_cost_ratio']) / 12; new_stress_index = (new_pmt + new_holding_cost) / params['monthly_income'] if params['monthly_income'] > 0 else 0
                        st.markdown(f"提高5%至 **{new_dp_ratio:.0%}**。")
                        st.markdown(f"<p style='color:green;'>➔ 壓力指數降至 <b>{new_stress_index:.1%}</b></p>", unsafe_allow_html=True)
                        if st.button("採納 D", key="optD", use_container_width=True): handle_suggestion_click({'down_payment_ratio': new_dp_ratio})
                col_idx += 1
                with cols[col_idx % 3]:
                    with st.container(border=True, height=200):
                        st.markdown("###### **方案E: 延長房貸年期**")
                        if params['mortgage_years'] < 40:
                            new_mortgage_years = 40
                            new_loan = params['target_house_price'] * (1 - params['down_payment_ratio']); new_pmt = calculate_pmt(new_loan, params['mortgage_rate']/12, new_mortgage_years*12)
                            new_holding_cost = (params['target_house_price'] * params['annual_holding_cost_ratio']) / 12; new_stress_index = (new_pmt + new_holding_cost) / params['monthly_income'] if params['monthly_income'] > 0 else 0
                            st.markdown(f"延長至 **{new_mortgage_years}** 年。")
                            st.markdown(f"<p style='color:green;'>➔ 壓力指數降至 <b>{new_stress_index:.1%}</b></p>", unsafe_allow_html=True)
                            if st.button("採納 E", key="optE", use_container_width=True): handle_suggestion_click({'mortgage_years': new_mortgage_years})
                        else:
                            st.markdown("房貸年期已達最長(40年)，此方案不適用。")
                col_idx += 1
                with cols[col_idx % 3]:
                    with st.container(border=True, height=200):
                        st.markdown("###### **方案F: 提升未來收入**")
                        new_income = int(params['monthly_income'] * 1.1)
                        new_stress_index = (p2_res['monthly_mortgage_payment'] + p2_res['monthly_holding_cost']) / new_income if new_income > 0 else 0
                        st.markdown(f"若月收入能提升10%至 **{new_income:,.0f}** 元。")
                        st.markdown(f"<p style='color:green;'>➔ 壓力指數降至 <b>{new_stress_index:.1%}</b></p>", unsafe_allow_html=True)
                        if st.button("採納 F", key="optF", use_container_width=True): handle_suggestion_click({'monthly_income': new_income})
                col_idx += 1

    with tab2:
        st.header("頭期款準備分析")
        st.markdown(f"您計畫在 **{params['prep_years_limit']}** 年內，從 **{format_large_number(params['initial_savings'])}** 的本金開始，每月投入 **{params['monthly_savings']:,}** 元，來達成 **{format_large_number(p1_res['target_down_payment'])}** 的頭期款目標。")
        m_col1, m_col2 = st.columns(2)
        m_col1.metric(f"在 {params['prep_years_limit']} 年內達標的機率", f"{p1_res['success_rate']:.1%}")
        m_col2.metric("成功者的平均達標時間", f"{p1_res['average_years']:.1f} 年" if p1_res['average_years'] else "N/A")
        fig1 = plot_accumulation_chart(p1_res['all_trajectories'], p1_res['target_down_payment'], params['prep_years_limit'], '頭期款財富累積軌跡')
        st.pyplot(fig1)

    with tab3:
        st.header("房貸與持有期分析")

        monthly_surplus = params['monthly_income'] - p2_res['monthly_mortgage_payment'] - p2_res['monthly_holding_cost'] - params['monthly_expenses']
        median_final_financial_assets = np.median(p2_res['final_financial_assets']) if p2_res['final_financial_assets'] else 0
        final_house_value = params['target_house_price']
        median_final_net_worth = final_house_value + median_final_financial_assets
        loan_amount = p2_res['loan_amount']
        total_mortgage_paid = p2_res['monthly_mortgage_payment'] * params['mortgage_years'] * 12
        total_interest_paid = total_mortgage_paid - loan_amount
        total_holding_cost = p2_res['monthly_holding_cost'] * params['mortgage_years'] * 12
        costs_dict = {'本金': params['target_house_price'], '利息': total_interest_paid, '持有成本': total_holding_cost}
        benefits_dict = {'房屋價值': final_house_value, '累積金融資產': median_final_financial_assets}
        net_gain_loss = sum(benefits_dict.values()) - sum(costs_dict.values())

        phase2_text_structured = f"""
#### 1. 每月現金流健康度評估
購屋後，您的每月現金流結構如下：
- **主要支出**：每月房貸還款額約為 **{format_large_number(p2_res['monthly_mortgage_payment'])}** 元，加上預估的房屋持有成本 **{format_large_number(p2_res['monthly_holding_cost'])}** 元，合計 **{format_large_number(p2_res['monthly_mortgage_payment'] + p2_res['monthly_holding_cost'])}** 元。
- **財務壓力指數**：綜合房屋相關支出後，您的財務壓力指數為 **{financial_stress_index:.1%}**。此數值是衡量購屋負擔是否過重的關鍵指標。
- **剩餘資金**：在支付房貸、持有成本與您設定的 **{format_large_number(params['monthly_expenses'])}** 元生活開銷後，每月預計能結餘 **{format_large_number(monthly_surplus)}** 元，可用於額外投資或應對突發狀況。
#### 2. 長期財務風險與機會分析
- **現金流耗盡風險**：在長達 **{params['mortgage_years']}** 年的模擬期間，考量到市場波動與各項支出，您的額外金融資產（來自每月結餘的投資）有 **{p2_res['asset_depletion_risk']:.1%}** 的機率會因市場下行或入不敷出而被耗盡。此風險值越低，代表您的財務計畫越穩健。
- **期末資產預估（中位數）**：若計畫順利，在 **{params['mortgage_years']}** 年房貸清償完畢時，您的財務狀況預計如下：
    - **房屋資產**：您將擁有價值 **{format_large_number(final_house_value)}** 元的房產。
    - **金融資產**：透過每月結餘的再投資，預計可累積約 **{format_large_number(median_final_financial_assets)}** 元的金融資產。
    - **總淨資產**：兩者相加，您的總淨資產中位數預計可達 **{format_large_number(median_final_net_worth)}**。
#### 3. 最終損益裁決
- **真實購屋總成本**：包含房屋本金、總利息與總持有成本，合計約 **{format_large_number(sum(costs_dict.values()))}** 元。
- **最終總淨資產**：房產價值加上累積的金融資產，合計約 **{format_large_number(sum(benefits_dict.values()))}** 元。
- **財務淨增值 / 減損**：最終裁決，此購屋決策預計將為您帶來約 **{format_large_number(net_gain_loss)}** 元的淨增長（或減損）。
"""
        phase2_text = phase2_text_structured
        st.markdown(phase2_text)
        st.divider()

        st.subheader("每月現金流儀表板")
        c1, c2 = st.columns([1.2, 1])
        with c1:
            with st.container(border=True):
                st.markdown("##### **每月現金流分析**")
                st.metric(label="💰 每月稅後總收入", value=f"{format_large_number(params['monthly_income'])} 元")
                st.metric(label="🏠 房貸與持有成本", value=f"- {format_large_number(p2_res['monthly_mortgage_payment'] + p2_res['monthly_holding_cost'])} 元")
                st.metric(label="🛒 每月固定生活支出", value=f"- {format_large_number(params['monthly_expenses'])} 元")
                st.divider()
                st.metric(label="🏦 每月剩餘可投資金額", value=f"{format_large_number(monthly_surplus)} 元", help="這是您每月收入扣除所有開銷後，能用於再投資或額外儲蓄的金額。若為負數，代表您的現金流將出現缺口。")
        with c2:
            pie_data = [p2_res['monthly_mortgage_payment'], p2_res['monthly_holding_cost'], params['monthly_expenses'], max(0, monthly_surplus)]
            pie_labels = ['房貸月付金', '房屋持有成本', '生活支出', '剩餘可投資']
            fig_pie = plot_cash_flow_pie(pie_data, pie_labels, params['monthly_income'])
            st.pyplot(fig_pie)

        st.subheader("購屋總成本及淨值效益分析")
        with st.container(border=True):
            st.markdown("這部分將深入剖析這筆購屋投資的長期財務後果，回答最終極的問題：**這間房子，是資產還是負債？**")
            fig_cost_benefit = plot_cost_benefit_analysis(costs_dict, benefits_dict)
            st.pyplot(fig_cost_benefit)
            st.divider()
            st.markdown("##### **最終財務損益裁決 (中位數)**")
            if net_gain_loss > 0:
                st.success(f"🎉 恭喜！這是一項正向投資。在 {params['mortgage_years']} 年後，您的購屋決策預計將帶來約 **{format_large_number(net_gain_loss)}** 元的財務淨增長。")
            else:
                st.warning(f"⚠️ 注意！這可能是一項負向投資。在 {params['mortgage_years']} 年後，您的購屋決策預計將導致約 **{format_large_number(abs(net_gain_loss))}** 元的財務淨減損。")
            st.caption("此計算為「最終總淨資產」減去「真實購屋總成本」，結果為正代表資產增長超過總支出，反之則代表總支出高於資產增長。")

        st.subheader("淨資產成長軌跡")
        fig2 = plot_net_worth_chart(p2_res['all_net_worth_trajectories'], params['mortgage_years'], '持有期總淨資產成長軌跡')
        st.pyplot(fig2)

    # --- PDF 報告生成與下載區塊 ---
    st.write("---")
    st.header("📥 下載完整報告")
    with st.spinner('正在產生PDF報告...'):
        # 1. 準備 PDF 報告所需的各章節純文字內容
        
        pdf_narrative_summary = strip_markdown_for_pdf(narrative_summary)
        pdf_summary_p1 = strip_markdown_for_pdf(f"第一階段評估：{p1_summary}")
        pdf_summary_p2 = strip_markdown_for_pdf(f"第二階段評估：{p2_summary}")

        phase1_text_for_pdf = f"""
在您的規劃中，計畫於 {params['prep_years_limit']} 年內，從 {format_large_number(params['initial_savings'])} 元的本金開始，每月投入 {format_large_number(params['monthly_savings'])} 元，來達成 {format_large_number(p1_res['target_down_payment'])} 元的頭期款目標。
根據我們的模擬分析，關鍵成果如下：
- 在 {params['prep_years_limit']} 年內達標的機率: {p1_res['success_rate']:.1%}
- 成功者的平均達標時間: {p1_res['average_years']:.1f} 年 (此為成功達標模擬路徑的平均值)
"""
        pdf_phase1_analysis = strip_markdown_for_pdf(phase1_text_for_pdf)
        
        phase2_main_text = strip_markdown_for_pdf(phase2_text)
        cash_flow_summary = f"""
每月現金流儀表板摘要:
- 每月稅後總收入: {format_large_number(params['monthly_income'])} 元
- 房貸與持有成本合計: -{format_large_number(p2_res['monthly_mortgage_payment'] + p2_res['monthly_holding_cost'])} 元
- 每月固定生活支出: -{format_large_number(params['monthly_expenses'])} 元
--------------------------------------------------
- 每月剩餘可投資金額: {format_large_number(monthly_surplus)} 元
"""
        if net_gain_loss > 0:
            final_verdict = f"最終財務損益裁決: 恭喜！這是一項正向投資。在 {params['mortgage_years']} 年後，您的購屋決策預計將帶來約 {format_large_number(net_gain_loss)} 元的財務淨增長。"
        else:
            final_verdict = f"最終財務損益裁決: 注意！這可能是一項負向投資。在 {params['mortgage_years']} 年後，您的購屋決策預計將導致約 {format_large_number(abs(net_gain_loss))} 元的財務淨減損。"
        
        pdf_phase2_analysis = f"{phase2_main_text}\n\n{cash_flow_summary}\n\n{final_verdict}"
        
        params_text_list = []
        for key, value in params.items():
            if key in ['initial_savings', 'monthly_savings', 'monthly_income', 'monthly_expenses', 'target_house_price']:
                params_text_list.append(f"- {key}: {format_large_number(value)} 元")
            elif key.endswith('_ratio') or key.endswith('_rate') or 'return' in key:
                 params_text_list.append(f"- {key}: {value:.2%}")
            elif key == 'simulations':
                 params_text_list.append(f"- {key}: {value:,} 次")
            else:
                params_text_list.append(f"- {key}: {value}")
        params_text = "\n".join(params_text_list)

        disclaimer_text = "名詞解釋:\n- 財務壓力指數: (每月房貸 + 每月持有成本) / 每月稅後總收入。衡量現金流的健康程度。\n- 淨資產: 金融資產 + 房屋市價 - 剩餘房貸。代表您真正的總財富。\n\n免責聲明:\n本報告結果基於蒙地卡羅模擬，僅為根據您輸入參數的統計推斷，並非投資建議或未來表現的保證。所有決策請諮詢專業財務顧問。"
        
        texts_for_pdf = {
            'narrative_summary': pdf_narrative_summary, 'summary_p1': pdf_summary_p1, 'summary_p2': pdf_summary_p2,
            'phase1_analysis': pdf_phase1_analysis, 'phase2_analysis': pdf_phase2_analysis,
            'params': params_text, 'disclaimer': disclaimer_text
        }
        
        # 2. 儲存所有需要的圖表
        fig_paths = {}
        try:
            fig_paths = {
                'phase1_chart_path': 'phase1_chart.png', 'phase2_chart_path': 'phase2_chart.png',
                'stress_gauge_path': 'stress_gauge.png', 'cost_benefit_path': 'cost_benefit.png',
                'cash_flow_pie_path': 'cash_flow_pie.png'
            }
            fig1.savefig(fig_paths['phase1_chart_path'], dpi=300, bbox_inches='tight')
            fig2.savefig(fig_paths['phase2_chart_path'], dpi=300, bbox_inches='tight')
            stress_gauge_fig.savefig(fig_paths['stress_gauge_path'], dpi=300, bbox_inches='tight')
            fig_cost_benefit.savefig(fig_paths['cost_benefit_path'], dpi=300, bbox_inches='tight')
            fig_pie.savefig(fig_paths['cash_flow_pie_path'], dpi=300, bbox_inches='tight')
            
            # 3. 生成 PDF
            pdf_data = create_pdf_report(params, texts_for_pdf, fig_paths)
            
            st.download_button(
                label="點此下載PDF報告", data=pdf_data, 
                file_name=f"Home_Purchase_Plan_v4.0_{datetime.now().strftime('%Y%m%d')}.pdf", 
                mime="application/pdf", use_container_width=True
            )
        finally:
            # 4. 清理暫存的圖檔
            for path in fig_paths.values():
                if os.path.exists(path):
                    os.remove(path)

else:
    st.info("👈 請在左方側邊欄設定您的財務參數，然後點擊「執行模擬分析」按鈕。")