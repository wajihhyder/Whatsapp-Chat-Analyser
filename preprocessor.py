import re
import pandas as pd

def preprocess(data):
    pattern = r'(\d{1,2}/\d{1,2}/\d{2,4},\s\d{1,2}:\d{2}\s(?:AM|PM)\s-\s)(.*?)\n(?=\d{1,2}/\d{1,2}/\d{2,4},\s\d{1,2}:\d{2}\s(?:AM|PM)\s-\s|\Z)'
    matches = re.findall(pattern, data)

    dates = [match[0].replace('\u202f', '') for match in matches]  # Remove \u202f from dates
    messages = [match[1] for match in matches]

    df = pd.DataFrame({'user_message': messages, 'message_date': dates})
    df['message_date'] = pd.to_datetime(df['message_date'], format='%m/%d/%y, %I:%M%p - ')
    df.rename(columns={'message_date': 'date'   }, inplace=True)

    users = []
    user_messages = []  # Renamed from 'messages' to avoid overwriting
    for message in df['user_message']:
        entry = re.split(r'([\w\s]+?):\s', message)  # Updated pattern to capture usernames with spaces
        if entry[1:]:  # user name
            users.append(entry[1])
            user_messages.append(" ".join(entry[2:]))
        else:
            users.append('group_notification')
            user_messages.append(entry[0])

    df['user'] = users
    df['message'] = user_messages
    df.drop(columns=['user_message'], inplace=True)

    df['only_date'] = df['date'].dt.date
    df['year'] = df['date'].dt.year
    df['month_num'] = df['date'].dt.month
    df['month'] = df['date'].dt.month_name()
    df['day'] = df['date'].dt.day
    df['day_name'] = df['date'].dt.day_name()
    df['hour'] = df['date'].dt.hour
    df['minute'] = df['date'].dt.minute

    period = []
    for hour in df[['day_name', 'hour']]['hour']:
        if hour == 23:
            period.append(str(hour) + "-" + str('00'))
        elif hour == 0:
            period.append(str('00') + "-" + str(hour + 1))
        else:
            period.append(str(hour) + "-" + str(hour + 1))

    df['period'] = period

    return df