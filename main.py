import requests
from bs4 import BeautifulSoup
from urllib.parse import quote
import csv
import re
import os
import time
import pandas as pd
import jieba
import jieba.analyse
from collections import Counter
import matplotlib.pyplot as plt
from wordcloud import WordCloud
import numpy as np
from PIL import Image

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'WenQuanYi Micro Hei']
plt.rcParams['axes.unicode_minus'] = False

# 读取cookie
with open('cookie.txt', 'r') as f:
    cookie = f.read().strip()

# 完整的请求头
headers = {
    'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
    'accept-language': 'zh-CN,zh;q=0.9',
    'cache-control': 'no-cache',
    'pragma': 'no-cache',
    'referer': 'https://passport.weibo.com/',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36',
    'cookie': cookie
}

keywords = '男童被机器人踢中腹部痛苦倒地'
encoded_keywords = quote(keywords, safe='')

session = requests.Session()
session.headers.update(headers)


def extract_weibo_data(html, page_num):
    """从HTML中提取微博数据"""
    soup = BeautifulSoup(html, 'html.parser')
    weibo_list = []

    # 查找所有微博卡片
    cards = soup.find_all('div', attrs={'action-type': 'feed_list_item'})

    if not cards:
        cards = soup.find_all('div', class_=re.compile(r'card-wrap'))

    print(f"第{page_num}页找到 {len(cards)} 条微博")

    for idx, card in enumerate(cards, 1):
        weibo_data = {
            '页码': page_num,
            '本页序号': idx,
            '用户昵称': '',
            '用户主页': '',
            '头像URL': '',
            '发布时间': '',
            '发布来源': '',
            '微博正文': '',
            '转发数': '',
            '评论数': '',
            '点赞数': '',
            '微博MID': '',
            '微博链接': ''
        }

        # 提取用户昵称和主页
        name_elem = card.select_one('.name')
        if name_elem:
            weibo_data['用户昵称'] = name_elem.get_text(strip=True)
            weibo_data['用户主页'] = name_elem.get('href', '')
            if weibo_data['用户主页'] and not weibo_data['用户主页'].startswith('http'):
                weibo_data['用户主页'] = 'https://weibo.com' + weibo_data['用户主页']

        # 提取头像URL
        avatar_elem = card.select_one('.avator img')
        if avatar_elem:
            avatar_url = avatar_elem.get('src', '')
            if avatar_url and not avatar_url.startswith('http'):
                avatar_url = 'https:' + avatar_url
            weibo_data['头像URL'] = avatar_url

        # 提取发布时间和来源
        from_elem = card.select_one('.from')
        if from_elem:
            time_elem = from_elem.select_one('a:first-child')
            if time_elem:
                weibo_data['发布时间'] = time_elem.get_text(strip=True)

            source_elem = from_elem.select_one('a:last-child')
            if source_elem and source_elem != time_elem:
                weibo_data['发布来源'] = source_elem.get_text(strip=True)

        # 提取微博正文
        content_full = card.select_one('.txt[node-type="feed_list_content_full"]')
        if content_full:
            weibo_data['微博正文'] = content_full.get_text(strip=True)
        else:
            content = card.select_one('.txt[node-type="feed_list_content"]')
            if content:
                weibo_data['微博正文'] = content.get_text(strip=True)

        # 清理正文
        if weibo_data['微博正文']:
            # 移除话题链接
            weibo_data['微博正文'] = re.sub(r'#.*?#', '', weibo_data['微博正文'])
            # 移除URL
            weibo_data['微博正文'] = re.sub(r'http\S+', '', weibo_data['微博正文'])
            # 移除@用户
            weibo_data['微博正文'] = re.sub(r'@\S+', '', weibo_data['微博正文'])

        # 提取互动数据
        forward_elem = card.select_one('[action-type="feed_list_forward"]')
        if forward_elem:
            forward_text = forward_elem.get_text(strip=True)
            if forward_text and forward_text != '转发':
                weibo_data['转发数'] = forward_text

        comment_elem = card.select_one('[action-type="feed_list_comment"]')
        if comment_elem:
            comment_text = comment_elem.get_text(strip=True)
            if comment_text and comment_text != '评论':
                weibo_data['评论数'] = comment_text

        like_elem = card.select_one('[action-type="feed_list_like"] .woo-like-count')
        if like_elem:
            like_text = like_elem.get_text(strip=True)
            if like_text and like_text != '赞':
                weibo_data['点赞数'] = like_text

        # 提取微博MID和链接
        mid = card.get('mid', '')
        weibo_data['微博MID'] = mid
        if mid:
            weibo_data['微博链接'] = f"https://weibo.com/{mid}"

        if weibo_data['用户昵称'] or weibo_data['微博正文']:
            weibo_list.append(weibo_data)

    return weibo_list


def append_to_csv(data, filename='weibo_data.csv'):
    """追加数据到同一个CSV文件"""
    if not data:
        return False

    file_exists = os.path.isfile(filename)

    with open(filename, 'a', newline='', encoding='utf-8-sig') as f:
        keys = data[0].keys()
        writer = csv.DictWriter(f, fieldnames=keys)

        if not file_exists:
            writer.writeheader()

        writer.writerows(data)

    return True


def get_total_pages(html):
    """从HTML中提取总页数"""
    soup = BeautifulSoup(html, 'html.parser')

    page_links = soup.select('.m-page .list a, .m-page .list li a')
    max_page = 1

    for link in page_links:
        page_text = link.get_text(strip=True)
        if page_text.isdigit():
            page_num = int(page_text)
            if page_num > max_page:
                max_page = page_num

    if max_page == 1:
        result_text = soup.find('div', class_='m-error')
        if result_text:
            text = result_text.get_text(strip=True)
            match = re.search(r'找到(\d+)条结果', text)
            if match:
                total_count = int(match.group(1))
                max_page = (total_count + 19) // 20
                print(f"根据总条数{total_count}计算，约{max_page}页")

    return max_page


def crawl_weibo_pages(start_page=1, max_pages=None, output_file='weibo_data.csv'):
    """爬取多页微博数据"""
    current_page = start_page
    total_extracted = 0

    if os.path.exists(output_file):
        print(f"文件 {output_file} 已存在，将追加新数据")

    while True:
        url = f'https://s.weibo.com/weibo?q=%23{encoded_keywords}%23&page={current_page}'
        print(f"\n{'=' * 60}")
        print(f"正在爬取第 {current_page} 页...")
        print(f"URL: {url}")

        try:
            response = session.get(url, timeout=10)
            response.encoding = 'utf-8'

            if response.status_code != 200:
                print(f"请求失败，状态码: {response.status_code}")
                break

            if 'Sina Visitor System' in response.text or '登录' in response.text:
                print(f"⚠️ 第{current_page}页被拦截，需要登录！")
                break

            page_data = extract_weibo_data(response.text, current_page)

            if not page_data:
                print(f"第{current_page}页没有提取到数据，可能已到最后")
                break

            append_to_csv(page_data, output_file)
            total_extracted += len(page_data)
            print(f"✓ 第{current_page}页已保存 ({len(page_data)}条)，累计{total_extracted}条")

            if current_page == start_page:
                total_pages = get_total_pages(response.text)
                if total_pages > start_page:
                    print(f"检测到总页数: {total_pages}")
                    if max_pages is None:
                        max_pages = total_pages
                    else:
                        max_pages = min(max_pages, total_pages)

            if max_pages and current_page >= max_pages:
                print(f"\n已达到最大页数 {max_pages}，停止爬取")
                break

            current_page += 1
            time.sleep(2)

        except requests.exceptions.RequestException as e:
            print(f"请求第{current_page}页失败: {e}")
            break

    print(f"\n{'=' * 60}")
    print(f"爬取完成！共处理 {current_page - start_page} 页，总计 {total_extracted} 条微博")
    print(f"数据已保存到: {output_file}")

    return output_file


def text_preprocessing(text):
    """文本预处理"""
    if pd.isna(text) or not text:
        return ""

    # 转换为字符串
    text = str(text)

    # 去除URL
    text = re.sub(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', '', text)

    # 去除话题标签
    text = re.sub(r'#.*?#', '', text)

    # 去除@用户
    text = re.sub(r'@[\w\u4e00-\u9fff]+', '', text)

    # 去除表情符号（保留文字）
    text = re.sub(r'\[.*?\]', '', text)

    # 去除标点符号和数字
    text = re.sub(r'[^\u4e00-\u9fa5]', '', text)

    # 去除空白字符
    text = re.sub(r'\s+', '', text)

    return text.strip()


def perform_analysis(csv_file='weibo_data.csv'):
    """执行数据分析和可视化"""

    print("\n" + "=" * 60)
    print("开始数据分析...")
    print("=" * 60)
    # 读取数据
    df = pd.read_csv(csv_file, encoding='utf-8-sig')
    print(f"\n共加载 {len(df)} 条微博数据")

    # 创建输出目录
    if not os.path.exists('analysis_results'):
        os.makedirs('analysis_results')

    # ==================== 1. 用户统计分析 ====================
    print("\n【1. 用户统计分析】")

    # 用户活跃度TOP10
    user_counts = df['用户昵称'].value_counts().head(10)
    print("\n活跃用户TOP10:")
    for user, count in user_counts.items():
        if user and user != '未知用户':
            print(f"  {user}: {count}条")

    # 保存用户统计
    user_counts.to_csv('analysis_results/user_activity_top10.csv', encoding='utf-8-sig')

    # 绘制用户活跃度柱状图
    if len(user_counts) > 0:
        plt.figure(figsize=(12, 6))
        user_counts.plot(kind='bar')
        plt.title('微博活跃用户TOP10', fontsize=16)
        plt.xlabel('用户昵称', fontsize=12)
        plt.ylabel('发布微博数量', fontsize=12)
        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()
        plt.savefig('analysis_results/user_activity_chart.png', dpi=300, bbox_inches='tight')
        plt.close()
        print("✓ 用户活跃度图表已保存")

    # ==================== 2. 发布时间分析 ====================
    print("\n【2. 发布时间分析】")

    # 提取时间信息
    df['发布时间_clean'] = df['发布时间'].astype(str)

    # 统计日期分布
    date_counts = df['发布时间_clean'].value_counts().head(20)
    print("\n发布时间分布TOP20:")
    for date, count in date_counts.head(10).items():
        if date and date != 'nan':
            print(f"  {date}: {count}条")

    # 绘制发布时间分布图
    if len(date_counts) > 0:
        plt.figure(figsize=(14, 6))
        date_counts.plot(kind='bar')
        plt.title('微博发布时间分布TOP20', fontsize=16)
        plt.xlabel('发布时间', fontsize=12)
        plt.ylabel('微博数量', fontsize=12)
        plt.xticks(rotation=45, ha='right', fontsize=8)
        plt.tight_layout()
        plt.savefig('analysis_results/post_time_distribution.png', dpi=300, bbox_inches='tight')
        plt.close()
        print("✓ 发布时间分布图已保存")

    # ==================== 3. 互动数据分析 ====================
    print("\n【3. 互动数据分析】")

    # 转换互动数据为数字
    for col in ['转发数', '评论数', '点赞数']:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # 总互动量
    total_forwards = df['转发数'].sum()
    total_comments = df['评论数'].sum()
    total_likes = df['点赞数'].sum()

    print(f"\n总互动量统计:")
    print(f"  总转发数: {int(total_forwards)}")
    print(f"  总评论数: {int(total_comments)}")
    print(f"  总点赞数: {int(total_likes)}")

    # 平均互动量
    avg_forwards = df['转发数'].mean()
    avg_comments = df['评论数'].mean()
    avg_likes = df['点赞数'].mean()

    print(f"\n平均互动量:")
    print(f"  平均转发数: {avg_forwards:.2f}")
    print(f"  平均评论数: {avg_comments:.2f}")
    print(f"  平均点赞数: {avg_likes:.2f}")

    # 互动量TOP10
    df['总互动'] = df['转发数'] + df['评论数'] + df['点赞数']
    top_interactive = df.nlargest(10, '总互动')[['用户昵称', '转发数', '评论数', '点赞数', '总互动']]
    top_interactive.to_csv('analysis_results/top_interactive_weibo.csv', index=False, encoding='utf-8-sig')
    print("\n✓ 互动量TOP10微博已保存")

    # 绘制互动量分布图
    plt.figure(figsize=(10, 6))
    plt.bar(['转发数', '评论数', '点赞数'], [total_forwards, total_comments, total_likes])
    plt.title('微博总互动量统计', fontsize=16)
    plt.xlabel('互动类型', fontsize=12)
    plt.ylabel('总数', fontsize=12)
    for i, v in enumerate([total_forwards, total_comments, total_likes]):
        plt.text(i, v + 10, str(int(v)), ha='center', va='bottom')
    plt.tight_layout()
    plt.savefig('analysis_results/interaction_summary.png', dpi=300)
    plt.close()
    print("✓ 互动量统计图已保存")

    # ==================== 4. 文本内容分析 ====================
    print("\n【4. 文本内容分析】")

    # 文本预处理
    print("正在进行文本预处理...")
    df['processed_text'] = df['微博正文'].apply(text_preprocessing)

    # 过滤空文本
    valid_texts = df[df['processed_text'] != '']['processed_text'].tolist()
    print(f"有效文本数量: {len(valid_texts)}")

    # 分词和词频统计
    print("正在进行分词处理...")
    all_words = []
    for text in valid_texts:
        words = jieba.cut(text)
        # 过滤单字词和停用词
        words = [w for w in words if len(w) >= 2]
        all_words.extend(words)

    # 词频统计
    word_freq = Counter(all_words)

    # 获取TOP50关键词
    top_words = word_freq.most_common(50)

    print("\n关键词TOP20:")
    for word, freq in top_words[:20]:
        print(f"  {word}: {freq}次")

    # 保存词频统计
    with open('analysis_results/word_frequency.csv', 'w', encoding='utf-8-sig') as f:
        f.write("词语,频次\n")
        for word, freq in top_words:
            f.write(f"{word},{freq}\n")
    print("✓ 词频统计已保存")

    # ==================== 5. 生成词云图 ====================
    print("\n【5. 生成词云图】")

    # 准备词频字典
    word_freq_dict = dict(top_words)

    # 生成词云
    try:
        # 使用圆形掩码
        mask = np.zeros((500, 500))

        wordcloud = WordCloud(
            width=1200,
            height=800,
            background_color='white',
            font_path='simhei.ttf',  # Windows系统
            # font_path='/System/Library/Fonts/PingFang.ttc',  # macOS系统
            max_words=200,
            relative_scaling=0.5,
            colormap='viridis',
            random_state=42
        ).generate_from_frequencies(word_freq_dict)

        # 保存词云图
        plt.figure(figsize=(16, 10))
        plt.imshow(wordcloud, interpolation='bilinear')
        plt.axis('off')
        plt.title(f'微博话题词云图 - {keywords}', fontsize=20, pad=20)
        plt.tight_layout()
        plt.savefig('analysis_results/wordcloud.png', dpi=300, bbox_inches='tight')
        plt.close()
        print("✓ 词云图已保存到 analysis_results/wordcloud.png")

    except Exception as e:
        print(f"词云图生成失败: {e}")
        print("尝试备用方案...")

        # 备用方案：不使用自定义字体
        try:
            wordcloud = WordCloud(
                width=1200,
                height=800,
                background_color='white',
                max_words=200,
                relative_scaling=0.5,
                colormap='viridis'
            ).generate_from_frequencies(word_freq_dict)

            plt.figure(figsize=(16, 10))
            plt.imshow(wordcloud, interpolation='bilinear')
            plt.axis('off')
            plt.title(f'微博话题词云图 - {keywords}', fontsize=20, pad=20)
            plt.tight_layout()
            plt.savefig('analysis_results/wordcloud.png', dpi=300, bbox_inches='tight')
            plt.close()
            print("✓ 词云图已保存（使用默认字体）")
        except Exception as e2:
            print(f"备用方案也失败: {e2}")

    # ==================== 6. 情感倾向简单分析 ====================
    print("\n【6. 情感倾向分析】")

    # 定义情感词库（简化版）
    positive_words = ['好', '支持', '希望', '安全', '赔偿', '负责', '关心', '没事', '万幸']
    negative_words = ['危险', '问题', '担心', '痛心', '愤怒', '失望', '冷漠', '寒心', '受伤', '痛苦']

    positive_count = 0
    negative_count = 0

    for text in valid_texts:
        for word in positive_words:
            if word in text:
                positive_count += 1
                break
        for word in negative_words:
            if word in text:
                negative_count += 1
                break

    print(f"\n情感倾向统计:")
    print(f"  正面情绪微博数: {positive_count}")
    print(f"  负面情绪微博数: {negative_count}")
    print(f"  中性情绪微博数: {len(valid_texts) - positive_count - negative_count}")

    # 绘制情感分布饼图
    if len(valid_texts) > 0:
        plt.figure(figsize=(8, 8))
        labels = ['正面情绪', '负面情绪', '中性情绪']
        sizes = [positive_count, negative_count, len(valid_texts) - positive_count - negative_count]
        colors = ['#ff9999', '#66b3ff', '#99ff99']
        plt.pie(sizes, labels=labels, colors=colors, autopct='%1.1f%%', startangle=90)
        plt.title('微博情感倾向分布', fontsize=16)
        plt.axis('equal')
        plt.savefig('analysis_results/sentiment_distribution.png', dpi=300, bbox_inches='tight')
        plt.close()
        print("✓ 情感分布图已保存")

    # ==================== 生成分析报告 ====================
    print("\n【7. 生成分析报告】")

    with open('analysis_results/analysis_report.txt', 'w', encoding='utf-8') as f:
        f.write("=" * 60 + "\n")
        f.write(f"微博话题数据分析报告\n")
        f.write(f"话题：{keywords}\n")
        f.write("=" * 60 + "\n\n")

        f.write("一、数据概况\n")
        f.write(f"  总微博数：{len(df)}条\n")
        f.write(f"  总页数：{df['页码'].max()}页\n\n")

        f.write("二、用户分析\n")
        f.write(f"  活跃用户数：{df['用户昵称'].nunique()}人\n")
        f.write("  活跃用户TOP5：\n")
        for user, count in user_counts.head(5).items():
            if user and user != '未知用户':
                f.write(f"    {user}：{count}条\n")
        f.write("\n")

        f.write("三、互动数据分析\n")
        f.write(f"  总转发数：{int(total_forwards)}\n")
        f.write(f"  总评论数：{int(total_comments)}\n")
        f.write(f"  总点赞数：{int(total_likes)}\n")
        f.write(f"  平均转发数：{avg_forwards:.2f}\n")
        f.write(f"  平均评论数：{avg_comments:.2f}\n")
        f.write(f"  平均点赞数：{avg_likes:.2f}\n\n")

        f.write("四、内容分析\n")
        f.write(f"  有效评论文本数：{len(valid_texts)}条\n")
        f.write("  关键词TOP10：\n")
        for word, freq in top_words[:10]:
            f.write(f"    {word}：{freq}次\n")
        f.write("\n")

        f.write("五、情感分析\n")
        f.write(f"  正面情绪：{positive_count}条 ({positive_count / len(valid_texts) * 100:.1f}%)\n")
        f.write(f"  负面情绪：{negative_count}条 ({negative_count / len(valid_texts) * 100:.1f}%)\n")
        f.write(
            f"  中性情绪：{len(valid_texts) - positive_count - negative_count}条 ({(len(valid_texts) - positive_count - negative_count) / len(valid_texts) * 100:.1f}%)\n")

    print("✓ 分析报告已保存到 analysis_results/analysis_report.txt")

    print("\n" + "=" * 60)
    print("数据分析完成！")
    print(f"所有结果已保存到 analysis_results/ 目录")
    print("=" * 60)

    # 显示文件列表
    print("\n生成的文件：")
    for file in os.listdir('analysis_results'):
        print(f"  - analysis_results/{file}")


if __name__ == "__main__":
    # 配置参数
    START_PAGE = 1  # 起始页
    MAX_PAGES = 30  # 最大页数（先爬3页测试，可以改成None爬全部）
    OUTPUT_FILE = 'weibo_data.csv'

    # 1. 爬取数据
    csv_file = crawl_weibo_pages(start_page=START_PAGE, max_pages=MAX_PAGES, output_file=OUTPUT_FILE)

    # 2. 数据分析
    if os.path.exists(csv_file):
        perform_analysis(csv_file)
    else:
        print("未找到数据文件，请先运行爬虫！")