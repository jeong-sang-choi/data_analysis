from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException, ElementClickInterceptedException
from selenium.webdriver.support import expected_conditions as EC

from bs4 import BeautifulSoup as bs
import pandas as pd
import time
from random import randint
import requests
from datetime import datetime
import pymysql
import uuid



print("Starting process...")

# 변수 선언
replica_database_host = '127.0.0.1'
replica_database_user = 'root'
replica_database_password = '0000'
replica_database_database = 'wello_data'
master_database_host = '127.0.0.1'
master_database_user = 'root'
master_database_password = '0000'
master_database_database = 'wello_data'

print("define database information")

# 데이터베이스 연결 설정
connection = pymysql.connect(
    host='127.0.0.1',
    user='root',
    password='0000',
    db='wello_data',
    charset='utf8mb4',
    cursorclass=pymysql.cursors.DictCursor
)


driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()))
url = 'https://www.jobaba.net/sprtPlcy/info/list2020.do'
url_fix = 'https://www.jobaba.net/sprtPlcy/info/view2020.do?seq='
driver.get(url)

print("셀레니움 환경 설정")

IDs_list = []
j = 3

select = driver.find_element(By.XPATH, '//*[@id="ex_select_1"]')
select.click()
option = select.find_element(By.XPATH, '//*[@id="ex_select_1"]/option[1]')
option.click()
time.sleep(2)

# 전체 약 10분 걸림

# 페이지 넘기면서 ID 크롤링
while True:
    # 페이지 ID 크롤링
    try:
        time.sleep(1.8)
        for i in range(1, 21):
            html = driver.page_source
            soup = bs(html, 'html.parser')
            hrefs = soup.select(f'#moreListWrap > li:nth-child({i}) > a')
            IDs_list.extend([href['onclick'].split("'")[1] for href in hrefs])
        j += 1
    except NoSuchElementException:
        print("Element not found, stopping process.")
        break
    
    # 다음 페이지로 이동
    try:
        nextBtn = driver.find_element(By.XPATH, f'//*[@id="content-side"]/div/ul/li[{j}]/a')
        nextBtn.click()
        # print(j)
        if j == 13: j = 3
        # if j == 4: break
    except NoSuchElementException:
        print("Next button not found, stopping process.")
        break
    except ElementClickInterceptedException:
        print("ElementClickInterceptedException, stopping process.")
        break

driver.quit()
IDs_list = list(set(IDs_list))

print('url done')

data_list = []
print('content start')

for ID in IDs_list:
    
    time.sleep(2)
    content = {'policy_name': '', 'agency': '', 'age_begin': '0', 'age_end': '99', 'income_begin': '0', 'income_end': '99999', 'administrative_rules': '', 'agency_apply': '', 'agency_tel': '', 'api_create': '', 'apply_documents': '', 'apply_url': '', 'base_rule': '', 'department': '', 'desc_age': '', 'desc_apply': '', 'desc_criteria': '', 'desc_service': '', 'desc_support': '', 'desc_target': '', 'due_date_begin': '', 'due_date_end': '', 'gov_service_id': '', 'info_url': '', 'local_gevernments_rules': '', 'priority': '16', 'create_at': '', 'create_id': '0', 'update_id': '0', 'update_at': '', 'inspection_status': '', 'policy_type_cd': '', 'support_benefit': '', 'inspection_completed_date': '', 'inspection_request_date': '', 'origin_policy_name': '', 'avail_delete_yn': 'Y', 'labeler_id': '', 'code_due_date_type': '', 'agency_type': '', 'desc_provision': '', 'origin': '', 'code_agency': '', 'id_idx': '', 'display_yn': 'Y', 'non_display_reason': ''}

    url = url_fix + ID
    response = requests.get(url)
    soup = bs(response.text, 'html.parser')

    Title = soup.find('div', {'class': 'list_t_area'}).find('p').text
    if '[' in Title:
        title = Title.split(']')
        content['policy_name'] = title[1].strip()
        content['origin_policy_name'] = title[1].strip()
        if title[0].replace('[', '').strip()[-1] == '시' or title[0].replace('[', '').strip()[-1] == '군':
            content['agency'] = '경기도 ' + title[0].replace('[', '').strip()
        else:
            content['agency'] = title[0].replace('[', '').strip() + ' 전체'
    else:
        content['policy_name'] = Title
        content['origin_policy_name'] = Title
    paragraphs_1_s_tit = soup.find_all('p', {'class': 's_tit'})
    paragraphs_1_note = soup.find_all('p', {'class': 'note'})
    table = soup.find('table')
    Details_2 = soup.find_all('div', {'class': 'tmp_wrap'})
    Details_3 = soup.find_all('div', {'class': 'list_area'})

    content['info_url'] = url
    content['gov_service_id'] = 'JOBABA' + ID
    content['id_idx'] = str(uuid.uuid4())
    # content['create_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    # content['update_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    # content['api_create'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')


    for i in range(0, 4):
        key = paragraphs_1_s_tit[i].text.strip()
        value = paragraphs_1_note[i].text.strip()
        # content[key] = value
        if key == '이용방법':
            # content['신청방법'] = value
            content['desc_apply'] = value

        if key == '모집일정':
            # content['모집기간_코드'] = []
            if value == '상시':
                year_start = datetime(datetime.now().year, 1, 1)
                year_end = datetime(datetime.now().year, 12, 31)
                content['due_date_begin'] = year_start.strftime('%Y-%m-%d')
                content['due_date_end'] = year_end.strftime('%Y-%m-%d')
                content['code_due_date_type'] = 'C15-01'
            elif '~' in value:
                start_date, end_date = value.split('~')
                start_date = start_date.split('(')[0].strip()
                end_date = end_date.split('(')[0].strip()
                content['due_date_begin'] = start_date.strip()
                content['due_date_end'] = end_date.strip()
                if content['due_date_end'] == '모집완료시':
                    content['code_due_date_type'] = 'C15-04'
                else:
                    content['code_due_date_type'] = 'C15-06'
            else:
                content['due_date_begin'] = ''
                content['due_date_end'] = ''
                content['code_due_date_type'] = ''
            # content['모집기간_코드'] = ', '.join(content['모집기간_코드'])

        if key == '지원대상':
            content['desc_criteria'] = value
            content['desc_target'] = value
    
    if table:
        rows = table.find_all('tr')
        for row in rows:
            th = row.find('th')
            td = row.find('td')
            if th and td:
                key = th.text.strip()
                value = td.text.strip()
                # content[key] = value
                if key == '지원기간':
                    content['desc_support'] += key + ': ' + value.replace('\n', ' ') + '\n'
                else:
                    # content['desc_support'] += key + ': ' + value + '\n'
                    continue
    
    for detail in Details_2:
        paragraphs_p = detail.find_all('p', {'class': 'tit'})
        paragraphs_ul = detail.find_all('ul', {'class': 'style_dot'})
        
        for p_tag, ul_tag in zip(paragraphs_p, paragraphs_ul):
            key = p_tag.text.strip()
            value = '\n'.join([li.text.strip() for li in ul_tag.find_all('li')])
            # content[key] = value
            key = key.split()[-1]
            if key == '사업정보':
                content['desc_support'] += '\n' + value
                continue
            elif key == '형태':
                # content['📂 채용분야 및 형태'] = value
                content['desc_support'] += '\n' + value
                continue
    
    for detail in Details_3:
        li_tags = detail.find_all('li')
        for index, li in enumerate(li_tags):
            if index == 0:
                p_tag = li.find('p', {'class': 's_tit wid80'})
                if p_tag:
                    p_tag_text = p_tag.text.strip()
                    content['agency_apply'] = p_tag_text.replace('기관명', '')
            elif index == 2:
                p_tag = li.find('p', {'class': 's_tit wid80'})
                if p_tag:
                    p_tag_text = p_tag.text.strip()
                    number = p_tag_text.replace('전화번호', '')
                    content['agency_tel'] = number.strip()

    data_list.append(content)

try:
    with connection.cursor() as cursor:
        for data in data_list:
            for key, value in data.items():
                if isinstance(value, str):
                    value = value.replace('\n', '').replace('\r', '').replace('\t', '').replace('\xa0', ' ')
                data[key] = value
            print(data)
            # print(len(data))

            select_query = "SELECT * FROM meta_policy WHERE meta_policy_id = %s"
            cursor.execute(select_query, (data.get('meta_policy_id'),))
            result = cursor.fetchone()
            if result:
                print(f"Skipping duplicate entry for meta_policy_id: {data.get('meta_policy_id')}")
                continue
            
            insert_query = """
            INSERT INTO meta_policy (
                                        policy_name, agency, age_begin, age_end, income_begin, 
                                        income_end, administrative_rules, agency_apply, agency_tel, apply_documents, 
                                        apply_url, base_rule, department, desc_age, desc_apply, 
                                        desc_criteria, desc_service, desc_support, desc_target, due_date_begin, 
                                        due_date_end, gov_service_id, info_url, local_gevernments_rules, priority, 
                                        inspection_status, policy_type_cd, support_benefit, 
                                        origin_policy_name, avail_delete_yn, labeler_id, code_due_date_type, agency_type, 
                                        desc_provision, origin, code_agency, id_
          --------------------------------

try:
    with connection.cursor() as cursor:
        for data in data_list:
            for key, value in data.items():
                if isinstance(value, str):
                    value = value.replace('\n', '').replace('\r', '').replace('\t', '').replace('\xa0', ' ')
                data[key] = value
            print(data)
            # print(len(data))

            select_query = "SELECT * FROM meta_policy WHERE meta_policy_id = %s"
            cursor.execute(select_query, (data.get('meta_policy_id'),))
            result = cursor.fetchone()
            if result:
                print(f"Skipping duplicate entry for meta_policy_id: {data.get('meta_policy_id')}")
                continue
            
            insert_query = """
            INSERT INTO meta_policy (
                                        policy_name, agency, age_begin, age_end, income_begin, 
                                        income_end, administrative_rules, agency_apply, agency_tel, apply_documents, 
                                        apply_url, base_rule, department, desc_age, desc_apply, 
                                        desc_criteria, desc_service, desc_support, desc_target, due_date_begin, 
                                        due_date_end, gov_service_id, info_url, local_gevernments_rules, priority, 
                                        inspection_status, policy_type_cd, support_benefit, 
                                        origin_policy_name, avail_delete_yn, labeler_id, code_due_date_type, agency_type, 
                                        desc_provision, origin, code_agency, id_idx, display_yn, 
                                        non_display_reason, create_at, create_id, update_id, update_at, api_create 
                                    )
                                    VALUES (
                                        %s,%s,%s,%s,%s,
                                        %s,%s,%s,%s,%s,
                                        %s,%s,%s,%s,%s,
                                        %s,%s,%s,%s,%s,
                                        %s,%s,%s,%s,%s,
                                        %s,%s,%s,
                                        %s,%s, 0, %s,%s,
                                        %s,%s,%s,%s,%s,
                                        %s, now(), 0, 0, now(), now()
                                    )
            """
            cursor.execute(insert_query, (
                data.get('policy_name', None), data.get('agency', None), data.get('age_begin', None), data.get('age_end', None),
                data.get('income_begin', None), data.get('income_end', None), data.get('administrative_rules', None), data.get('agency_apply', None),
                data.get('agency_tel', None), data.get('apply_documents', None), data.get('apply_url', None), data.get('base_rule', None),
                data.get('department', None), data.get('desc_age', None), data.get('desc_apply', None), data.get('desc_criteria', None), data.get('desc_service', None),
                data.get('desc_support', None), data.get('desc_target', None), data.get('due_date_begin', None), data.get('due_date_end', None),
                data.get('gov_service_id', None), data.get('info_url', None), data.get('local_gevernments_rules', None), data.get('priority', None),
                data.get('inspection_status', None), data.get('policy_type_cd', None), data.get('support_benefit', None), 
                data.get('origin_policy_name', None), data.get('avail_delete_yn', None),
                data.get('code_due_date_type', None), data.get('agency_type', None), data.get('desc_provision', None), data.get('origin', None), data.get('code_agency', None),
                data.get('id_idx', None), data.get('display_yn', None), data.get('non_display_reason', None)
            ))
        connection.commit()  
        print("Data inserted successfully!")
except Exception as e:
    print(f"Error inserting data: {e}")

connection.close()
