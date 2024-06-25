import datetime
import pandas as pd
import pymysql
import itertools
import requests
import sys
import random
from bs4 import BeautifulSoup
import math
import uuid

sys.path.append('.')
from settings import settings


def get_uuid(try_cnt, origin_id):
    fn_connect = pymysql.Connect(host=replica_host, user=replica_username, password=replica_password,
                                 port=replica_port, database=replica_database)
    fn_cursor = fn_connect.cursor()
    idx = str(uuid.uuid4())
    id_idx_query = f"select id_idx from meta_business where id_idx = '{idx}'"
    fn_cursor.execute(id_idx_query)
    id_idx_data = fn_cursor.fetchall()
    cursor.close()
    if id_idx_data == ():
        return idx
    elif try_cnt >= 1000:
        return origin_id
    else:
        get_uuid(try_cnt + 1, origin_id)


# 환경변수 불러오기
master_host = settings.DATASOURCE_MASTER_HOST
master_username = settings.DATASOURCE_MASTER_USERNAME
master_password = settings.DATASOURCE_MASTER_PASSWORD
master_port = settings.DATASOURCE_MASTER_PORT
master_database = settings.DATASOURCE_MASTER_DATABASE
replica_host = settings.DATASOURCE_REPLICA_HOST
replica_username = settings.DATASOURCE_REPLICA_USERNAME
replica_password = settings.DATASOURCE_REPLICA_PASSWORD
replica_port = settings.DATASOURCE_REPLICA_PORT
replica_database = settings.DATASOURCE_REPLICA_DATABASE
# slack
env_emoji = settings.SLACK_PRODUCTION_IMOJI
slack_webhood_channel_url = settings.SLACK_WEBHOOK_CHANNEL
slack_error_channel_url = settings.SLACK_ERROR_CHANNEL

naver_channel_id = settings.NAVER_WEBHOOK
hook_api_url = settings.HOOK_API_URL

# slack webhook
slack_url = slack_webhood_channel_url
slack_payload_start = {
    "text": f"{env_emoji} {datetime.datetime.now().strftime('%Y-%m-%d %H시 %M분')}\n\n:sijak: 웰로비즈 아이리스 데이터 수집 시작"}
requests.post(slack_url, json=slack_payload_start)

hook_params = {
    'channel_id': naver_channel_id,
    'message': "[웰로비즈] IRIS 데이터 수집 시작",
    'success_yn': 'true'
}
requests.post(url=hook_api_url, json=hook_params)

begin_at = datetime.datetime.now()

# 전체 페이지 수 조회
iris_url = 'https://www.iris.go.kr/contents/retrieveBsnsAncmBtinSituListView.do'
business_count_request = requests.get(iris_url)
business_count_html = BeautifulSoup(business_count_request.text, 'html.parser')

business_count = int(business_count_html.select_one('div.board_info span.total_page b').text)
page_number = math.ceil(business_count / 10)

iris_business_dict = {}

try:
    # 공고목록 조회
    for i in range(page_number):
        business_list_url = f'https://www.iris.go.kr/contents/retrieveBsnsAncmBtinSituListView.do?pageIndex={i + 1}'
        business_list_request = requests.get(business_list_url)
        business_list_html = BeautifulSoup(business_list_request.text, 'html.parser')
        row_count = 10
        if (i + 1 == page_number) & (business_count % 10 != 0):
            row_count = business_count % 10
        # 공고 리스트 데이터 추출
        for row in range(row_count):
            # id, status 추출
            iris_attr = business_list_html.select_one(
                'div.tstyle.list.biz_announce ul li:nth-child({}) div div.group1 strong a'.format(row + 1))
            iris_attr = iris_attr.get_attribute_list('onclick')[0]
            iris_attr = iris_attr.replace('f_bsnsAncmBtinSituListForm_view', '').replace(' return false;', '')
            iris_attr = iris_attr.replace("'", '').replace('(', '').replace(')', '').replace(';', '').split(',')
            iris_id = iris_attr[0]
            iris_status = iris_attr[1]
            # 공고명 추출
            policy_name = business_list_html.select_one(
                'div.tstyle.list.biz_announce ul li:nth-child({}) div  div.group1  strong  a'.format(row + 1)).text
            # 기관명 추출
            agency = business_list_html.select_one(
                'div.tstyle.list.biz_announce ul li:nth-child({}) span'.format(row + 1)).text
            agency = agency.split(' > ')[1]
            # info_url 추출
            info_url = 'https://www.iris.go.kr/contents/retrieveBsnsAncmView.do?ancmId={}&ancmPrg={}'.format(
                iris_id, iris_status)
            iris_business_dict[iris_id] = {'status': iris_status,
                                           'policy_name': policy_name,
                                           'agency': agency,
                                           'info_url': info_url,
                                           'gov_service_id': 'IRIS{}'.format(iris_id)}

    iris_dataframe = pd.DataFrame(iris_business_dict).transpose()

    # 기간 데이터
    for i in iris_dataframe.index:
        iris_detail_url = iris_dataframe.loc[i, 'info_url']
        iris_detail_request = requests.get(iris_detail_url)
        iris_detail_html = BeautifulSoup(iris_detail_request.text, 'html.parser')
        date_range = iris_detail_html.select_one('div.tstyle_view > div.title_area > ul > li:nth-child(6) > span').text
        date_range = date_range.replace(' ', '').replace('\r', '').replace('\n', '')
        date_range = date_range.split('~')
        due_date_begin = '{} 09:00:00'.format(date_range[0])
        due_date_end = '{} 15:00:00'.format(date_range[1])
        iris_dataframe.loc[i, 'due_date_begin'] = due_date_begin
        iris_dataframe.loc[i, 'due_date_end'] = due_date_end

    iris_dataframe['origin'] = '범부처통합연구지원시스템(IRIS)'




    # DB연결 - 레플리카
    connect = pymysql.Connect(host=replica_host, user=replica_username, password=replica_password,
                              port=replica_port, database=replica_database)
    cursor = connect.cursor()

    # 중복데이터 조회
    meta_business_duplicate_check_query = """select meta_business_id, gov_service_id 
                                             from meta_business
                                             where gov_service_id in {}""".format(tuple(iris_dataframe['gov_service_id']))
    cursor.execute(meta_business_duplicate_check_query)
    meta_business_gov_service_id_load = cursor.fetchall()
    meta_business_dataframe = pd.DataFrame(meta_business_gov_service_id_load, columns=['meta_business_id', 'gov_service_id'])
    connect.close()

    # 데이터 필터링
    iris_insert_dataframe = iris_dataframe[
        ~iris_dataframe['gov_service_id'].isin(meta_business_dataframe['gov_service_id'].tolist())
    ].reset_index(drop=True)

    # 입력자 지정
    labeler_list = [257770, 247459, 299263]  # 247459(김영미) 257770(신영하) 299263(전영운)
    random.shuffle(labeler_list)
    labeler_pool = itertools.cycle(labeler_list)

    iris_insert_dataframe['labeler_id'] = ''
    for i in range(len(iris_insert_dataframe)):
        iris_insert_dataframe.loc[i, 'labeler_id'] = next(labeler_pool)

    iris_insert_dataframe['id_idx'] = None

    for i in range(len(iris_insert_dataframe)):
        target_id = iris_insert_dataframe.loc[i, 'gov_service_id']
        iris_insert_dataframe.loc[i, 'id_idx'] = get_uuid(0, target_id)

    # 데이터 적재
    iris_insert_dataframe = iris_insert_dataframe[['gov_service_id',
                                                   'policy_name',
                                                   'agency',
                                                   'info_url',
                                                   'origin',
                                                   'due_date_begin',
                                                   'due_date_end',
                                                   'labeler_id',
                                                   'id_idx']]

    if len(iris_insert_dataframe) == 0:
        payload_none_data = {"text": f"""{env_emoji}:suc:{datetime.datetime.now().strftime('%Y-%m-%d %H시 %M분')}
    - 아이리스 최초 수집데이터: {len(iris_dataframe)}
    - 중복제거 이후 데이터: {len(iris_insert_dataframe)}
    :finish: 웰로비즈 아이리스 수집 종료"""}

        hook_params = {
            'channel_id': naver_channel_id,
            'message': "[웰로비즈] IRIS 데이터 수집 종료\n수집데이터 0건",
            'success_yn': 'true'
        }
        requests.post(url=hook_api_url, json=hook_params)

        requests.post(slack_webhood_channel_url, json=payload_none_data)
        # batch_execute table insert
        terminated_at = datetime.datetime.now()
        batch_summary = f'[{datetime.datetime.now().strftime("%Y-%m-%d")}] 아이리스 데이터 수집 종료'
        batch_trace = "수집데이터 0건"
        # database connect
        connect = pymysql.Connect(host=master_host, user=master_username, password=master_password,
                                  port=master_port, database=master_database)
        cursor = connect.cursor()
        dynamic_data = (begin_at.strftime('%Y-%m-%d %H:%M:%S'), terminated_at.strftime('%Y-%m-%d %H:%M:%S'),
                        int((terminated_at - begin_at).microseconds / 1000), batch_summary, batch_trace)
        batch_execute_table_insert_query = """insert into batch_execute(batch_id,
                        success, begin_at, terminated_at, executed, summary, trace)
                        values ('DATA_WELLOBIZ_COLLECT_IRIS', true, %s, %s, %s, %s, %s)"""
        cursor.execute(batch_execute_table_insert_query, dynamic_data)
        connect.commit()
        connect.close()

    else:
        iris_tuple = list(zip(*map(iris_insert_dataframe.get, iris_insert_dataframe)))
        # 데이터 적재
        connect = pymysql.Connect(host=master_host, user=master_username, password=master_password,
                                  port=master_port, database=master_database)
        cursor = connect.cursor()
        insert_query = """insert ignore into meta_business(gov_service_id,
                                                           policy_name,
                                                           agency,
                                                           info_url,
                                                           origin,
                                                           due_date_begin,
                                                           due_date_end,
                                                           labeler_id,
                                                           id_idx,
                                                           create_id,
                                                           update_id,
                                                           create_at,
                                                           update_at,
                                                           inspection_status,
                                                           year_founding_end,
                                                           age_end,
                                                           obstacle_yn,
                                                           apply_caution)
                          values(%s, %s, %s, %s, %s, %s, %s, %s, %s, 0, 0, now(), now(), 'INSPECTION_STATUS_LABELLING',
                                 99, 99, 'N', '○ 제외대상')"""
        cursor.executemany(insert_query, iris_tuple)
        connect.commit()
        connect.close()
        payload_success = {"text": f"""{env_emoji}:suc:{datetime.datetime.now().strftime('%Y-%m-%d %H시 %M분')}
    - 아이리스 최초 수집데이터: {len(iris_dataframe)}
    - 중복제거 이후 데이터: {len(iris_insert_dataframe)}
    :finish: 웰로비즈 아이리스 수집 완료"""}
        requests.post(slack_webhood_channel_url, json=payload_success)

        hook_params = {
            'channel_id': naver_channel_id,
            'message': f"[웰로비즈] IRIS 데이터 수집 성공\n수집데이터: {len(iris_insert_dataframe)}건",
            'success_yn': 'true'
        }
        requests.post(url=hook_api_url, json=hook_params)

        # batch_execute table insert
        terminated_at = datetime.datetime.now()
        batch_summary = f'[{datetime.datetime.now().strftime("%Y-%m-%d")}] 아이리스 데이터 수집 성공: {len(iris_insert_dataframe)}건'
        batch_trace = f"""최초 수집 데이터: {len(iris_dataframe)} 
        중복제거 이후 데이터: {len(iris_insert_dataframe)}"""
        # database connect
        connect = pymysql.Connect(host=master_host, user=master_username, password=master_password,
                                  port=master_port, database=master_database)
        cursor = connect.cursor()
        dynamic_data = (begin_at.strftime('%Y-%m-%d %H:%M:%S'), terminated_at.strftime('%Y-%m-%d %H:%M:%S'),
                        int((terminated_at - begin_at).microseconds / 1000), batch_summary, batch_trace)
        batch_execute_table_insert_query = """insert into batch_execute(batch_id,
                        success, begin_at, terminated_at, executed, summary, trace)
                        values ('DATA_WELLOBIZ_COLLECT_IRIS', true, %s, %s, %s, %s, %s)"""
        cursor.execute(batch_execute_table_insert_query, dynamic_data)
        connect.commit()
        connect.close()

except Exception as err:
    _, _, tb = sys.exc_info()
    payload_error = {"text": f"""{env_emoji}:fail:{datetime.datetime.now().strftime('%Y-%m-%d %H시 %M분')}
- Unexpected {err=}: {type(err)=}
:finish: 웰로비즈 아이리스 수집 실패"""}
    requests.post(slack_error_channel_url, json=payload_error)

    hook_params = {
        'channel_id': naver_channel_id,
        'message': f"[웰로비즈] IRIS 수집 실패\n에러코드: {err}\n에러발생위치: {tb.tb_lineno}",
        'success_yn': 'false'
    }
    requests.post(url=hook_api_url, json=hook_params)

    # batch_execute table insert
    terminated_at = datetime.datetime.now()
    batch_summary = f'[{datetime.datetime.now().strftime("%Y-%m-%d")}] 아이리스 데이터 수집 실패'
    batch_trace = f"""Unexpected {err=}: {type(err)=}"""
    # database connect
    connect = pymysql.Connect(host=master_host, user=master_username, password=master_password,
                              port=master_port, database=master_database)
    cursor = connect.cursor()
    dynamic_data = (begin_at.strftime('%Y-%m-%d %H:%M:%S'), terminated_at.strftime('%Y-%m-%d %H:%M:%S'),
                    int((terminated_at - begin_at).microseconds / 1000), batch_summary, batch_trace)
    batch_execute_table_insert_query = """insert into batch_execute(batch_id,
            success, begin_at, terminated_at, executed, summary, trace)
            values ('DATA_WELLOBIZ_COLLECT_IRIS', false, %s, %s, %s, %s, %s)"""
    cursor.execute(batch_execute_table_insert_query, dynamic_data)
    connect.commit()
    connect.close()

    pass
