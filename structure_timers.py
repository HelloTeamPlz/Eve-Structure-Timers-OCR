import os
from datetime import datetime, timezone
import easyocr
import re

class StructureBot:
    
    def __init__() -> None:
        pass
    
    def get_channel_id(channel_name):
        """
        gets the channel id from env file
        """
        channel_id = os.environ.get(f"{channel_name}")
        return int(channel_id)
    
    def to_unix_time(date_time):
        unix_time = int(datetime.timestamp(date_time))
        return unix_time

    def timer(time):
        """
        given a string that looks like text, text and time stamp split on the "," parse the list to find the timestamp convert the timestamp into short and relitive date format
        for discod and return a tuple with all the desired values
        take curr unix time - future unix time + 900 (15 minm)
        """
        pattern = r'(\d{4}[.-]\d{2}[.-]\d{2} \d{2}[.:]\d{2}[.:]\d{2})'

        # Search for the pattern in the message
        match = re.search(pattern, time)

        if match:
            # Extract the matched date and time string
            date_time_str = match.group(1)

            # Convert the date and time string to a datetime object
            date_time_str = re.sub(r'[-.]', '.', date_time_str)
            dt_structure_timer = datetime.strptime(date_time_str, '%Y.%m.%d %H:%M:%S')
            unix_structure_timer = StructureBot.to_unix_time(dt_structure_timer)
            # Remove the date and time portion from the message
            cleaned_message = re.sub(pattern, '', time).strip()

            return (cleaned_message, unix_structure_timer)
        else:
            return print('f')
    
    def date_from_list(ocr_results):
        for i in ocr_results:
            # Use re.search to find the date and time pattern in the string
            match = re.search(r'\d{4}\.\d{2}\.\d{2} \d{2}\.\d{2}', i)
            if match:
                # Extract the matched pattern and parse it into a datetime object
                datetime_str = match.group()
                datetime_format = '%Y.%m.%d %H.%M'
                try:
                    parsed_datetime = datetime.strptime(datetime_str, datetime_format)
                    return parsed_datetime
                except ValueError:
                    # Handle ValueError in case of an invalid datetime format
                    pass

        return None

    def read_img(image_path):
        reader = easyocr.Reader(['en'], gpu = False)
        preprocessed_image = image_path
        results = reader.readtext(preprocessed_image, detail=0)
        return results
    
    def ocr_timer(timer):
        unix_structure_timer = StructureBot.to_unix_time(timer)
        current_unix_time = StructureBot.unix_time_now()
        seconds_till_timer = unix_structure_timer - current_unix_time + 900
        return seconds_till_timer

    def find_timers_txt(file_path):
        result = ''
        try:
            with open(file_path, 'r') as file:
            # Iterate through each line in the file
                for line in file:
                    # Split the line on ":"
                    parts = line.strip().split(':')
                    if len(parts) == 2:
                        # Add the two parts separated by ":" to the result
                        result += f"> {parts[1]} <t:{parts[0]}:f> in <t:{parts[0]}:R>\n"
            return result
        except FileNotFoundError:
            pass
        except Exception as e:
            pass 
        
    def find_time_left(file_path):
        try:
            t = StructureBot.find_timers_txt(file_path)
            current_unix_time = StructureBot.unix_time_now()
            timers = t.split('\n')
            tc = timers[-1].split(':')
            
            time_left = int(tc[1]) - current_unix_time
            return time_left
        except FileNotFoundError:
            pass
        except Exception as e:
            pass 
        
    def unix_time_now():
        current_unix_time = StructureBot.to_unix_time(datetime.now(timezone.utc))
        return current_unix_time
    
    def timer_to_dict(timer_map, results, timer_args):
        parsed_datetime = StructureBot.date_from_list(results)
        unix_ts = StructureBot.to_unix_time(parsed_datetime)
        timer_map.update({unix_ts: timer_args})
        #sort the timers and retrieve from the dictionary
        sorted_timers = timer_map(sorted(dict.items(), reverse=True))
        timers_msg = '\n'.join([f'> {value} <t:{key}:f> in <t:{key}:R> ID: {key}' for key, value in sorted_timers.items()])
        return timers_msg
    
    def write_to_timers_txt(msg):
        with open('timers.txt', 'w') as file:
            file.write(msg)
        file.close()