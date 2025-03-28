from urlextract import URLExtract
from wordcloud import WordCloud
import re
import pandas as pd
from collections import Counter
import emoji
import regex as reg

extract = URLExtract()

def fetch_stats(selected_users, df):
    if selected_users != 'Overall':
        df = df[df['user'] == selected_users]

    num_messages = df.shape[0]
    words = []
    for message in df['message']:
        words.extend(message.split())

    num_media = df[df['message'] == '<Media omitted>'].shape[0]

    links = []
    for message in df['message']:
        links.extend(extract.find_urls(message))

    return num_messages, len(words), num_media, len(links)

def most_busy_users(df):
    x = df['user'].value_counts().head()
    df = round((df['user'].value_counts() / df.shape[0]) * 100, 2).reset_index().rename(
        columns={'index': 'name', 'user': 'percent'})
    return x,df

def preprocess_text(text):
    # Remove URLs
    text = re.sub(r'http\S+', '', text)
    text = re.sub(r'\bnull\b', '', text)
    # Remove "Media omitted" and "Omitted media"
    text = text.replace("Media omitted", "").replace("Omitted media", "")
    return text

def create_wordcloud(selected_users, df):
    if selected_users != 'Overall':
        df = df[df['user'] == selected_users]

    # Concatenate all messages into a single string
    text = df['message'].str.cat(sep=" ")

    # Preprocess the text
    text = preprocess_text(text)

    # Create a WordCloud object with desired parameters
    wc = WordCloud(width=500, height=500, min_font_size=10, background_color='white',)

    # Generate the word cloud from the preprocessed text
    wc.generate(text)

    # Save the word cloud as an image file
    image_file_path = "wordcloud.png"
    wc.to_file(image_file_path)

    return image_file_path

def most_common_words(selected_users, df):
    f = open('stop_hinglish.txt', 'r')
    stop_words = f.read()

    if selected_users != 'Overall':
        df = df[df['user'] == selected_users]

    temp = df[df['user'] != 'group notification']
    temp = temp[temp['message'] != '<Media omitted>']

    words = []

    for message in temp['message']:
        for word in message.lower().split():
            # Check if word is not in stop words and not null or '/'
            if word not in stop_words and word != '' and word != '/' and word != 'null':
                words.append(word)

    return_df = pd.DataFrame(Counter(words).most_common(20))
    return return_df

def emoji_helper(selected_users, df):
    if selected_users != 'Overall':
        df = df[df['user'] == selected_users]

    emojis = []
    for message in df['message']:
        emojis.extend(reg.findall(r'\X', message))

    # Define Unicode ranges for emojis
    emoji_ranges = [
        ('\U0001F300', '\U0001F5FF'),  # Symbols & Pictographs
        ('\U0001F600', '\U0001F64F'),  # Emoticons
        ('\U0001F680', '\U0001F6FF'),  # Transport & Map Symbols
        ('\U0001F700', '\U0001F77F'),  # Alchemical Symbols
        ('\U0001F780', '\U0001F7FF'),  # Geometric Shapes Extended
        ('\U0001F800', '\U0001F8FF'),  # Supplemental Symbols and Pictographs
        ('\U0001F900', '\U0001F9FF'),  # Emoticons
        ('\U0001FA00', '\U0001FA6F'),  # Supplemental Symbols and Pictographs
        ('\U0001FA70', '\U0001FAFF'),  # Symbols and Pictographs Extended-A
        ('\U00002702', '\U000027B0'),  # Dingbats
        ('\U000024C2', '\U0001F251')   # Enclosed Characters
    ]

    emoji_chars = [c for c in emojis if any(start <= c <= end for start, end in emoji_ranges)]
    emoji_df = pd.DataFrame(Counter(emoji_chars).most_common(len(Counter(emoji_chars))))

    return emoji_df

def monthly_timeline(selected_users,df):

    if selected_users != 'Overall':
        df = df[df['user'] == selected_users]

    timeline = df.groupby(['year', 'month_num', 'month']).count()['message'].reset_index()

    time = []
    for i in range(timeline.shape[0]):
        time.append(timeline['month'][i] + "-" + str(timeline['year'][i]))

    timeline['time'] = time

    return timeline

def daily_timeline(selected_users,df):

    if selected_users != 'Overall':
        df = df[df['user'] == selected_users]

    daily_timeline = df.groupby('only_date').count()['message'].reset_index()

    return daily_timeline

def week_activity_map(selected_users,df):

    if selected_users != 'Overall':
        df = df[df['user'] == selected_users]

    return df['day_name'].value_counts()

def month_activity_map(selected_users,df):

    if selected_users != 'Overall':
        df = df[df['user'] == selected_users]

    return df['month'].value_counts()

def activity_heatmap(selected_users,df):

    if selected_users != 'Overall':
        df = df[df['user'] == selected_users]

    user_heatmap = df.pivot_table(index='day_name', columns='period', values='message', aggfunc='count').fillna(0)

    return user_heatmap