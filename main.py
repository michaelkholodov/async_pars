import asyncio
import base64
import json
import aiohttp
import datetime
import aiofiles

from bs4 import BeautifulSoup

from slugify import slugify
from transliterate import translit

API_CATEGORY = 'http://127.0.0.1:8000/api/category/?format=json'
API_GOODS = 'http://127.0.0.1:8000/api/goods/?format=json'
URL_2 = 'https://ukrzoloto.ua'

USERNAME = 'kholodov'
PASSWORD = '12345'

def translit_word(name):
    return translit(name, 'ru', reversed=True)

async def req_body(url, session):
    async with session.get(url) as resp:
        body = await resp.text()
        return body

async def post_api(url, session, data):
    async with session.post(url, json=data) as resp:
        response_data = await resp.json()
        if 'detail' in response_data and 'already exists' in response_data['detail']:
            # Якщо категорія вже існує, отримуємо її id
            existing_category = await session.get(f"{API_CATEGORY}?name={data['name']}")
            existing_category_data = await existing_category.json()
            if existing_category_data:
                return {'name': existing_category_data[0]['name'], 'id': existing_category_data[0]['id']}
        print(response_data)
        return response_data

async def get_authenticated_session(username, password):
    async with aiohttp.ClientSession() as session:
        auth_response = await session.post('http://127.0.0.1:8000/api/token/', data={'username': username, 'password': password})
        auth_data = await auth_response.json()
        access_token = auth_data.get('access')
        headers = {'Authorization': f'Bearer {access_token}'}
        return aiohttp.ClientSession(headers=headers)

async def download_image(good_img_url, session):
    async with session.get(good_img_url) as resp:
        img_data = await resp.read()
        b_img = base64.b64encode(img_data).decode('utf-8')
        return b_img

async def parse(session):
    startTime = datetime.datetime.now()
    print('Start')

    content = await req_body(URL_2 + '/catalog', session)
    bs = BeautifulSoup(content, 'html5lib')

    for item in bs.findAll("a", {"class": "catalogue-categories__link"}):
        name = item.get_text().strip()
        if name == 'Сертификаты':
            continue

        category_json = {
            'name': name,
            'activate': True,
            'url': str(item),
        }
        print(name)

        category = await post_api(API_CATEGORY, session, category_json)
        if 'id' in category:
            category_id = category['id']
        else:
            category_id = category.get('id')

        if not category_id:
            print(f"Failed to create category: {name}")
            continue

        good_url = URL_2 + item['href']
        goods_content = await req_body(good_url, session)
        bs1 = BeautifulSoup(goods_content, 'html5lib')
        goods = bs1.findAll("div", {"class": "product-card__content"})
        for index, good_item in enumerate(goods):
            good_name = good_item.select_one('.title').get_text().strip()
            good_img_url = good_item.select_one('.image')['src']
            good_price = good_item.select_one('.price__current span').get_text().replace(' ', '')
            price_opt = good_item.select_one('.price__old span').get_text().replace(' ', '')

            goods_json = {
                'category': category_id,
                'name': f'{good_name}',
                'description': translit_word(good_name),
                'price_opt': price_opt,
                'price': good_price,
                'activate': True,
                'image': await download_image(good_img_url, session)
            }
            await post_api(API_GOODS, session, goods_json)

    print("Used time:", datetime.datetime.now() - startTime)

async def main():
    session = await get_authenticated_session(USERNAME, PASSWORD)
    await parse(session)
    await session.close()

if __name__ == '__main__':
    asyncio.run(main())