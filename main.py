import os
from itertools import count
from typing import Union, Generator

import requests
from dotenv import load_dotenv
from terminaltables import AsciiTable


def get_hh_vacancies_count(url: str, params: dict, headers: dict) -> int:
    """Return vacancies count from hh.ru."""
    page_response = requests.get(url, headers=headers, params=params)
    page_response.raise_for_status()
    return page_response.json()['found']


def get_sj_vacancies_count(url: str, params: dict, headers: dict) -> int:
    """Return vacancies count from superjob.ru."""
    page_response = requests.get(url, headers=headers, params=params)
    page_response.raise_for_status()
    return page_response.json()['total']


def fetch_hh_vacancies(url: str, params: dict,
                       headers: dict) -> Generator[dict, None, None]:
    """Create genarator of vacancies from hh.ru"""
    for page in count():
        params['page'] = page
        page_response = requests.get(url, headers=headers, params=params)
        page_response.raise_for_status()
        page_data = page_response.json()

        if page >= page_data['pages'] or page == 199:
            break

        yield from page_data['items']


def fetch_sj_vacancies(url: str, params: dict,
                       headers: dict) -> Generator[dict, None, None]:
    """Create genarator of vacancies from superjob.ru"""
    for page in count():
        params['page'] = page
        page_response = requests.get(url, headers=headers, params=params)
        page_response.raise_for_status()
        page_data = page_response.json()

        if page >= page_data['total'] / params['count'] or page == 49:
            break

        yield from page_data['objects']


def predict_salary(salary_from: Union[None, int],
                   salary_to: Union[None, int]) -> Union[None, int]:
    """Return vacancy's approx salary."""
    if salary_from and salary_to:
        return int((salary_from + salary_to) / 2)
    else:
        if salary_from:
            return int(salary_from * 1.2)
        if salary_to:
            return int(salary_to * 0.8)
    return None


def predict_rub_salary_hh(vacancy: dict) -> Union[None, int]:
    """Return vacancy's approx salary in rubles for hh.ru."""
    salary = vacancy['salary']
    if salary is None:
        return None
    if salary['currency'] == 'RUR':
        salary_from = salary['from']
        salary_to = salary['to']
        return predict_salary(salary_from, salary_to)
    return None


def predict_rub_salary_sj(vacancy: dict) -> Union[int, None]:
    """Return vacancy's approx salary in rubles for superjob.ru."""
    if vacancy['currency'] == 'rub':
        salary_from = vacancy['payment_from']
        salary_to = vacancy['payment_to']
        return predict_salary(salary_from, salary_to)
    return None


def get_hh_statistics(languages: list[str], url: str, params: dict,
                    headers: dict) -> str:
    """
    Get statictics of vacancies and average salary for programming 
    language for hh.ru.
    """
    hh_statistics = []
    for language in languages:
        params['text'] = language
        vacancies_processed = 0
        salaries_sum = 0
        for vacancy in fetch_hh_vacancies(url, params, headers):
            if predict_rub_salary_hh(vacancy) is not None:
                vacancies_processed += 1
                salaries_sum += predict_rub_salary_hh(vacancy)
        hh_statistics.append(
            [
                language,
                get_hh_vacancies_count(url, params, headers),
                vacancies_processed,
                int(salaries_sum / vacancies_processed)
            ]
        )
    return hh_statistics


def get_sj_statistics(languages: list[str], url: str, params: dict,
                    headers: dict) -> str:
    """
    Get statictics of vacancies and average salary for programming 
    language for superjob.ru.
    """
    sj_statistics = []
    for language in languages:
        params['keyword'] = language
        vacancies_processed = 0
        salaries_sum = 0
        for vacancy in fetch_sj_vacancies(url, params, headers):
            if predict_rub_salary_sj(vacancy) is not None:
                vacancies_processed += 1
                salaries_sum += predict_rub_salary_sj(vacancy)
        sj_statistics.append(
            [
                language,
                get_sj_vacancies_count(url, params, headers),
                vacancies_processed,
                int(salaries_sum / vacancies_processed)
            ]
        )
    return sj_statistics


def create_table(table_name: str, table_data: list) -> str:
    """Create terminal table."""
    table_header = [
            [
                'Язык программирования',
                'Вакансий найдено',
                'Вакансий обработано',
                'Средняя зарплата'
            ]
    ]
    for language_statistics in table_data:
        table_header.append(language_statistics)
    table = AsciiTable(table_header, table_name)
    return table.table


def main() -> None:
    """Print average salary tables for hh.ru and superjob.ru."""
    load_dotenv()
    hh_url = 'https://api.hh.ru/vacancies'
    hh_params = {
        'period': 30,
        'specialization': 1,
        'area': 1,
        'professional_role': 96,
        'per_page': 10,
    }
    hh_headers = {'User-Agent': 'GetSalaries (rainbowf@mail.ru)'}
    hh_table_name = 'HeadHunter Moscow'
    
    sj_url = 'https://api.superjob.ru/2.0/vacancies/'
    sj_key = os.getenv('SJ_KEY')
    sj_params = {
        'town': 4,
        'catalogues': 48,
        'count': 10,
        'period': 7,
    }
    sj_headers = {
        'X-Api-App-Id': sj_key,
    }
    sj_table_name = 'SuperJob Moscow'

    programming_languages = [
        'JavaScript', 'Python', 'Java', 'C#', 'PHP', 'C++',
        'C', 'Ruby', 'Go'
    ]

    hh_statistics = get_hh_statistics(programming_languages, hh_url,
                                      hh_params, hh_headers)
    sj_statistics = get_sj_statistics(programming_languages, sj_url,
                                      sj_params, sj_headers)

    terminal_tables = (create_table(hh_table_name, hh_statistics),
                       create_table(sj_table_name, sj_statistics))
    print(*terminal_tables, sep='\n')


if __name__ == '__main__':
    main()
