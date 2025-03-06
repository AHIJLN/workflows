import os
import imaplib
import email
from email.utils import parsedate_to_datetime
from email.message import EmailMessage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from zoneinfo import ZoneInfo  # Python 3.9+；若低版本请使用 pytz
from datetime import datetime
import requests
import smtplib
import re
import os

# ===== 配置参数 =====
IMAP_SERVER = 'imap.mail.me.com'
SMTP_SERVER = 'smtp.mail.me.com'
EMAIL_ACCOUNT = 'lanh_1jiu@icloud.com'
APP_PASSWORD = os.environ.get('EMAIL_PASSWORD')  # 应用专用密码，从环境变量获取

# 垃圾箱文件夹名称（根据文件夹列表，iCloud 的垃圾箱一般为 "Deleted Messages"）
TRASH_FOLDER = '"Deleted Messages"'
ALTERNATE_TRASH = '"Trash"'

# Deepseek R1 API 配置（请根据实际接口文档修改）
DEEPSEEK_API_URL = 'https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions'
DEEPSEEK_API_KEY = os.environ.get('DEEPSEEK_API_KEY')

# 修改B_content为新的提示词
B_content = (
    "你是一个顶级问题分析专家，你把下面的内容，按以下表格来归类并解析以及思维导图（在邮件正文中能正常显示的表格和思维导图）。\n"
    "| 类別 | 随想 | 解析 |\n"
    "|------|------|------|\n"
    "|类別1|……|……|\n"
    "|      |……|……|\n"
    "|类別2|……|……|\n"
    "|      |……|……|\n\n"
    "请在回答中使用HTML格式创建表格和思维导图，确保它们能在标准邮件客户端中正确显示。"
    "对于思维导图，请使用简单的HTML和CSS来实现，不要使用复杂的JavaScript或外部库。"
)

def get_email_body(msg):
    """
    从 email.message 对象中提取文本内容，优先 text/plain，其次尝试 text/html。
    """
    body_plain = ""
    body_html = ""

    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            disp = str(part.get("Content-Disposition") or "")
            if 'attachment' in disp.lower():
                continue
            charset = part.get_content_charset() or 'utf-8'
            if content_type == 'text/plain':
                try:
                    body_plain += part.get_payload(decode=True).decode(charset, errors='replace')
                except Exception:
                    body_plain += part.get_payload(decode=True).decode('utf-8', errors='replace')
            elif content_type == 'text/html':
                try:
                    body_html += part.get_payload(decode=True).decode(charset, errors='replace')
                except Exception:
                    body_html += part.get_payload(decode=True).decode('utf-8', errors='replace')
    else:
        content_type = msg.get_content_type()
        charset = msg.get_content_charset() or 'utf-8'
        if content_type == 'text/plain':
            try:
                body_plain = msg.get_payload(decode=True).decode(charset, errors='replace')
            except Exception:
                body_plain = msg.get_payload(decode=True).decode('utf-8', errors='replace')
        elif content_type == 'text/html':
            try:
                body_html = msg.get_payload(decode=True).decode(charset, errors='replace')
            except Exception:
                body_html = msg.get_payload(decode=True).decode('utf-8', errors='replace')

    if body_plain.strip():
        return body_plain
    elif body_html.strip():
        return body_html
    else:
        return ""

def fetch_emails_in_time_range_uid(mail, start_hour=8, end_hour=22):
    """
    使用 UID 模式检索收件箱中所有邮件，
    筛选出当天（北京时间）且在 start_hour（含）到 end_hour（不含）之间的邮件，
    返回列表 [(uid_str, email.message 对象), ...]
    """
    status, data = mail.uid('search', None, 'ALL')
    if status != 'OK':
        print("无法搜索邮件 (UID)")
        return []
    uid_list = data[0].split()
    if not uid_list:
        print("收件箱为空")
        return []

    selected = []
    now_beijing = datetime.now(ZoneInfo("Asia/Shanghai"))
    today_date = now_beijing.date()

    for uid in uid_list:
        uid_str = uid.decode() if isinstance(uid, bytes) else str(uid)
        status, msg_data = mail.uid('fetch', uid_str, '(BODY[])')
        if status != 'OK' or not msg_data:
            print(f"获取邮件 UID={uid_str} 失败")
            continue

        content = None
        for part in msg_data:
            if isinstance(part, tuple) and part[1] and isinstance(part[1], bytes):
                content = part[1]
                break
        if not content:
            print(f"邮件 UID={uid_str} 没有有效内容")
            continue

        try:
            msg = email.message_from_bytes(content)
        except Exception as e:
            print(f"解析邮件 UID={uid_str} 失败: {e}")
            continue

        date_str = msg.get("Date")
        if not date_str:
            continue
        try:
            email_dt = parsedate_to_datetime(date_str)
            beijing_dt = email_dt.astimezone(ZoneInfo("Asia/Shanghai"))
        except Exception as e:
            print(f"解析邮件 UID={uid_str} 时间失败: {e}")
            continue

        if beijing_dt.date() == today_date and start_hour <= beijing_dt.hour < end_hour:
            selected.append((uid_str, msg))
        else:
            print(f"邮件 UID={uid_str} 时间 {beijing_dt} 不在目标范围")
    return selected

def call_deepseek_api(prompt):
    """
    调用 Deepseek R1 API，将 prompt 放入 messages 参数，并传入 temperature、top_p、max_tokens 参数。
    从返回结果中提取生成的文本内容。
    """
    prompt = prompt.strip()
    if not prompt:
        prompt = B_content
    print("DEBUG: Prompt内容为：", repr(prompt[:200]), "...(截断)")
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {DEEPSEEK_API_KEY}'
    }
    data = {
        "model": "deepseek-r1",
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "temperature": 1.0,
        "top_p": 0.9,
        "max_tokens": 2000,
         "language": "zh-CN"
    }
    try:
        resp = requests.post(DEEPSEEK_API_URL, headers=headers, json=data)
        if resp.status_code == 200:
            js = resp.json()
            return js['choices'][0]['message']['content']
        else:
            print("Deepseek API 错误:", resp.text)
            return ""
    except Exception as e:
        print("调用 Deepseek API 异常:", e)
        return ""

def send_email(subject, body, to_email):
    """
    使用 SMTP 发送HTML格式邮件，支持表格和思维导图。
    """
    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = EMAIL_ACCOUNT
    msg['To'] = to_email
    
    text_part = extract_plain_text_from_html(body)
    msg.attach(MIMEText(text_part, 'plain'))
    msg.attach(MIMEText(body, 'html'))
    
    try:
        with smtplib.SMTP(SMTP_SERVER, 587) as smtp:
            smtp.starttls()
            smtp.login(EMAIL_ACCOUNT, APP_PASSWORD)
            smtp.send_message(msg)
        print("HTML格式邮件发送成功")
    except Exception as e:
        print("发送邮件失败:", e)

def extract_plain_text_from_html(html_content):
    """
    从HTML内容中提取简单的纯文本表示，作为备用内容
    """
    text = html_content
    text = text.replace("<table", "\n").replace("</table>", "\n")
    text = text.replace("<tr", "\n").replace("</tr>", "")
    text = text.replace("<td", "\t").replace("</td>", "")
    text = text.replace("<th", "\t").replace("</th>", "")
    text = text.replace("<br>", "\n").replace("<br/>", "\n")
    text = text.replace("<div", "\n").replace("</div>", "\n")
    text = re.sub(r'<[^>]*>', '', text)
    return text


def ensure_html_format(api_result):
    """
    确保API返回结果是HTML格式的，如果不是则转换。
    支持表格和简单的思维导图。
    """
    # 如果返回的内容已经含有完整的HTML标签，则认为是HTML格式
    if "<html" in api_result.lower() and "</html>" in api_result.lower():
        return api_result

    # 如果只有表格标签但没有完整HTML结构
    if "<table" in api_result.lower() and "</table>" in api_result.lower():
        return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        table {{ border-collapse: collapse; width: 100%; margin-bottom: 20px; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #f2f2f2; }}
        .mindmap {{ margin-top: 20px; }}
        .mindmap-node {{ padding: 10px; border: 1px solid #ccc; border-radius: 5px; margin: 5px; }}
        .mindmap-main {{ background-color: #e6f2ff; }}
        .mindmap-sub {{ background-color: #f2f2f2; margin-left: 30px; }}
    </style>
</head>
<body>
    {api_result}
</body>
</html>
"""


# 如果是Markdown格式的表格，转换为HTML表格
    if "|---" in api_result:
        html_content = convert_markdown_to_html(api_result)
        return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        table {{ border-collapse: collapse; width: 100%; margin-bottom: 20px; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #f2f2f2; }}
        .mindmap {{ margin-top: 20px; }}
        .mindmap-node {{ padding: 10px; border: 1px solid #ccc; border-radius: 5px; margin: 5px; }}
        .mindmap-main {{ background-color: #e6f2ff; }}
        .mindmap-sub {{ background-color: #f2f2f2; margin-left: 30px; }}
    </style>
</head>
<body>
    {html_content}
</body>
</html>
"""

    # 默认情况，将纯文本包装在HTML中
    return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; }}
        p {{ margin-bottom: 16px; }}
    </style>
</head>
<body>
    <div>
        {api_result.replace("\\n", "<br/>")}
    </div>
</body>
</html>
"""

def create_simple_mindmap_html(topic, subtopics):
    """
    创建简单的思维导图HTML
    """
    html = '<div class="mindmap">\n'
    html += f'<div class="mindmap-node mindmap-main">{topic}</div>\n'
    for subtopic in subtopics:
        html += f'<div class="mindmap-node mindmap-sub">{subtopic}</div>\n'
    html += '</div>'
    return html

def main():
    """
    主程序函数，连接邮件服务器，处理当天邮件
    """
    try:
        print(f"开始连接到 {IMAP_SERVER}")
        mail = imaplib.IMAP4_SSL(IMAP_SERVER)
        mail.login(EMAIL_ACCOUNT, APP_PASSWORD)
        status, folders = mail.list()
        if status == 'OK':
            print("文件夹列表：")
            for f in folders:
                print(f.decode())
        mail.select('INBOX')

        print("检查今日邮件...")
        emails = fetch_emails_in_time_range_uid(mail)

        if not emails:
            print("没有找到今日邮件")
            mail.logout()
            return

        print(f"找到 {len(emails)} 封今日邮件，处理中...")

        # 收集邮件内容形成A_content，同时收集发件人、主题等信息
        A_content = ""
        uids_to_trash = []
        from_addresses = set()
        subjects = []

        for uid, msg in emails:
            body = get_email_body(msg)
            if not body:
                print(f"邮件 UID={uid} 正文为空，跳过")
                continue

            subject = msg.get('Subject', '')
            subject_decoded = email.header.decode_header(subject)[0][0]
            if isinstance(subject_decoded, bytes):
                subject_decoded = subject_decoded.decode('utf-8', errors='replace')
            subjects.append(subject_decoded)

            from_addr = msg.get('From', '')
            clean_from = from_addr.split('<')[-1].split('>')[0] if '<' in from_addr else from_addr
            from_addresses.add(clean_from)

            A_content += f"\n--- 邮件主题：{subject_decoded} ---\n{body}\n"
            uids_to_trash.append(uid)

        if not A_content.strip():
            print("没有收集到有效邮件内容")
            mail.logout()
            return

        print("DEBUG: A_content拼接后长度=", len(A_content))
        print("DEBUG: A_content前200字符:\n", repr(A_content[:200]), "\n")

        # 生成C内容：B内容放前面，然后追加A内容
        C_content = f"{B_content}\n\n以下是需要分析的内容：\n{A_content}"
        print("DEBUG: C_content前200字符:\n", repr(C_content[:200]), "\n")

        # 调用Deepseek API，将C内容作为Prompt传入
        print("调用 Deepseek R1 API，请稍候...")
        api_result = call_deepseek_api(C_content)
        if not api_result:
            print("API返回结果为空")
            mail.logout()
            return

        # 确保API返回结果为HTML格式
        html_result = ensure_html_format_final(api_result)

        # 构造回复邮件主题，并发送至所有来源邮箱
        reply_subject = f"今日邮件分析结果 - {datetime.now(ZoneInfo('Asia/Shanghai')).strftime('%Y-%m-%d')}"
        for from_addr in from_addresses:
            send_email(reply_subject, html_result, from_addr)
            print(f"已发送分析结果到 {from_addr}")

        # 将处理过的邮件移至垃圾箱
        if uids_to_trash:
            print(f"移动 {len(uids_to_trash)} 封处理过的邮件到垃圾箱")
            move_emails_to_trash_uid(mail, uids_to_trash)

        print("所有邮件处理完成")
        mail.logout()

    except Exception as e:
        print(f"程序运行出错: {e}")

if __name__ == "__main__":
    main()
