import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import requests
import os
import logging
from datetime import datetime, timedelta
import time

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("email_sender.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 邮件设置
EMAIL_HOST = "smtp.mail.me.com"
EMAIL_PORT = 587
EMAIL_USER = "lanh_1jiu@icloud.com"
EMAIL_PASSWORD = os.environ.get('EMAIL_PASSWORD')
EMAIL_RECIPIENT = "lanh_1jiu@icloud.com"
EMAIL_SUBJECT = "来自未来的一封信"

# Deepseek API设置
DEEPSEEK_API_KEY = os.environ.get('DEEPSEEK_API_KEY')
DEEPSEEK_API_URL = "https://ark.cn-beijing.volces.com/api/v3/bots/chat/completions"  # 请验证正确的API端点

# 你想要提交给Deepseek API的提示词
PROMPT = """
你是一个专业的谈判专家和顶级心理医生顾问，有10年丰富经验并拯救了100000个轻生少年少女和中老年人（这些内容不能在信中提及），请你写一封300汉字的信，用来鼓励抑郁症的病人。
请根据MECE原则来确保生成的内容，与之前所有版本完全不同，不重复以前的生成内容。
一、任务：
你的任务是以10年后成功的自己的口吻，给过去的自己(男，35岁，程序员)写一封信300汉字的鼓励信，一定要轻松自然，以防被识破，不能提过去的自己相关的生活细节，一定要让过去的自己重燃生活的希望，并且过好今天，并且承诺明天都会给过去的自己发一封邮件，让过去的自己好好过完今天，期待明天，署名为未来的自己。

二、回答格式要求：
1.开头为：致过去的我：(换行)，以「未来的你」结尾(只以"未来的你”，后面不能写任何内容）
三、回答内容要求：
1.正文内容不能出现：药物、自杀、割腕、具体的细节、具体的物件、具体地名、具体植物名、具体动物名、咖啡
2.邮件内容要按照以下示例来撰写：
示例样式1：
            十年后的今天，我迎来了全新的开始。回望过去的岁月，你曾面对无数挑战与困惑，但正是那段经历，塑造了今天坚韧而温暖的心。如今，我站在未来的路口，带着平静与希望，看见每一天都充满无限可能。过去的你或许曾感到疲惫迷茫，仿佛前路漫长无光。然而，请相信，每一个清晨都是重燃希望的时刻，每一份努力都将开花结果。勇敢地面对生活的风雨，不畏艰难，踏实走好每一步。今天的坚持，会成为明日成功的基石。记住，无论遇到怎样的坎坷，温柔的光总会驱散阴霾。你值得拥有美好的生活和温暖的未来。今后，我将每日写信与你分享微小的喜悦与感悟，陪伴你走过孤单与困境。让每个平凡的日子都变成希望的起点，点滴改变终将汇聚成幸福的海洋。请放下过去的沉重负担，轻装上阵，迎接新的挑战。生活或许曲折，但心中的梦想永远明亮。愿你在每个日落与日出间，找到内心的宁静与满足。未来的你已在前方等候，用坚定与热情拥抱每一个今天。期待与你再次相见，共同见证明日的辉煌。未来的路充满未知，但请记住，你绝不孤单，所有的坚持都会化作温暖的光芒。今日的每一分努力，都会成就明天的无限可能。愿你心怀希望，笑对风云，勇敢前行。你每天都在成长，我欣喜。
示例样式2：
        我是十年后的你。别急，先给自己一点时间，学会温柔对待内心的痛。抑郁并非软弱，而是一种需要耐心应对的过程。走过黑暗，你将发现光依然闪亮；经历迷茫，你会看清道路的方向。请相信，人生的转折往往在不经意间出现，只要你始终敞开心扉，慢慢地，你会发现自己比想象中更坚强。我知道你可能独自面对许多疑惑和恐慌，但绝不要轻言放弃。未来的我想告诉你，每一个明天都值得期待，而你所付出的努力，也会在时光的打磨下开出花朵。从现在开始，请试着关注周遭的小小美好，用心感受呼吸和心跳，给予自己谅解，也给世界一点信任。我将每天写一封邮件给你，让你知道你并不孤单；愿你勇敢度过今日，也期待更好的明天。记住，你正一步步成为更优秀的自己。未来已经为你准备好温暖与希望，我会在此等待与你相逢。
请不要纠结曾经的遗憾，也不必害怕未知的旅程。人生的章节不会只停留在那一页，只要你给自己机会，就能发现新的光芒。你会懂得，明日仍有风雨，但你要相信，心底的希望之火不会轻易熄灭。让每个当下都成为新的起点，给自己力量。记住，我会在你身边，不离不弃。若有疑惑，就告诉自己，明天的信里还会有回答。只要你肯相信，生活自会一步步拥抱你。
"""

def get_content_from_deepseek():
    """从Deepseek API获取生成的内容"""
    try:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}"
        }
        
        payload = {
            "model": "bot-20250307212922-8zvxp",  # 根据Deepseek的实际模型名称调整
            "messages": [
                {
                    "role": "user",
                    "content": PROMPT
                }
            ],
                "temperature": 1.5,  # 增加温度值，提高随机性
                "top_p": 0.9,        # 添加top_p参数
                "max_tokens": 600
        }
        
        response = requests.post(DEEPSEEK_API_URL, headers=headers, json=payload)
        response.raise_for_status()  # 如果请求失败会抛出异常
        
        result = response.json()
        generated_content = result['choices'][0]['message']['content']
        logger.info("成功从Deepseek获取内容")
        return generated_content
    
    except Exception as e:
        logger.error(f"从Deepseek获取内容时出错: {str(e)}")
        return f"获取内容失败: {str(e)}"

def send_email():
    """发送包含Deepseek内容的邮件"""
    try:
        # 获取当前日期并加上10年
        current_date = datetime.now()
        future_date = current_date.replace(year=current_date.year + 10)
        formatted_future_date = future_date.strftime("%Y年%m月%d日")
        
        # 获取Deepseek生成的内容
        content = get_content_from_deepseek()
        # 预先处理内容，将换行符替换为 <br>
        formatted_content = content.replace('\n', '<br>')
        
        # 创建邮件
        msg = MIMEMultipart()
        msg['From'] = EMAIL_USER
        msg['To'] = EMAIL_RECIPIENT
        msg['Subject'] = f"{EMAIL_SUBJECT} - {formatted_future_date}"
        
        # 添加邮件内容
        email_body = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; }}
                .container {{ padding: 15px; }}
                .header {{ color: #333366; font-size: 18px; font-weight: bold; }}
                .content {{ margin-top: 15px; line-height: 1.5; }}
                .footer {{ margin-top: 20px; font-size: 12px; color: #666; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header"></div>
                <div class="content">{formatted_content}</div>
                <div class="footer">你会越来越好，越来越完美</div>
            </div>
        </body>
        </html>
        """
        
        msg.attach(MIMEText(email_body, 'html'))
        
        # 连接到SMTP服务器并发送邮件
        with smtplib.SMTP(EMAIL_HOST, EMAIL_PORT) as server:
            server.starttls()  # 启用TLS加密
            server.login(EMAIL_USER, EMAIL_PASSWORD)
            server.send_message(msg)
        
        logger.info(f"邮件已成功发送至 {EMAIL_RECIPIENT}")
    
    except Exception as e:
        logger.error(f"发送邮件时出错: {str(e)}")

def main():
    """主函数，设置一次性定时任务，仅当天23:45运行"""
    logger.info("启动一次性邮件发送程序")
    
    # 获取当前时间
    now = datetime.now()
    
    # 设置目标时间 - 今天的0点1
    target_time = now.replace(hour=0, minute=1, second=0, microsecond=0)
    
    # 如果当前时间已经过了今天的0点，则立即执行
    if now > target_time:
        logger.info("已经过了指定的运行时间，立即执行任务")
        send_email()
        logger.info("任务执行完毕，程序退出")
        return
    
    # 计算等待时间（秒）
    wait_seconds = (target_time - now).total_seconds()
    
    logger.info(f"将在 {wait_seconds} 秒后运行任务（今天0:01）")
    
    # 等待到指定时间
    time.sleep(wait_seconds)
    
    # 到达指定时间后执行发送邮件
    send_email()
    
    logger.info("任务执行完毕，程序退出")

if __name__ == "__main__":
    main()
