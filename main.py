import os
from itertools import count
from typing import Union, Generator

import requests
from dotenv import load_dotenv
from terminaltables import AsciiTable


def fetch_hh_vacancies(hh_header: str, hh_professional_role_id: int,
        hh_specialization_id: int, language: str,
        vacancy_count_per_page: int, hh_area_id: int,
        hh_period: int) -> Generator[tuple[dict, int], None, None]:
    """Create generator of vacancies from hh.ru"""
    for page in count():
        page_response = requests.get(
            url='https://api.hh.ru/vacancies',
            headers={
                'User-Agent': hh_header,
            },
            params={
                'period': hh_period,
                'specialization': hh_specialization_id,
                'area': hh_area_id,
                'professional_role': hh_professional_role_id,
                'per_page': vacancy_count_per_page,
                'page': page,
                'text': language,
            }
        )
        page_response.raise_for_status()
        page_data = page_response.json()

        if page >= page_data['pages'] or page == 199:
            break
        
        for vacancy in page_data['items']:
            yield vacancy, page_data['found']


def fetch_sj_vacancies(language: str, sj_catalogues_id: int,
        sj_key: str, vacancy_count_per_page: int, sj_town_id: int,
        sj_period: int) -> Generator[tuple[dict, int], None, None]:
    """Create generator of vacancies from superjob.ru"""
    for page in count():
        page_response = requests.get(
            url='https://api.superjob.ru/2.0/vacancies/',
            headers={
                'X-Api-App-Id': sj_key,
            },
            params={
                'town': sj_town_id,
                'catalogues': sj_catalogues_id,
                'count': vacancy_count_per_page,
                'period': sj_period,
                'page': page,
                'keyword': language,
            }
        )
        page_response.raise_for_status()
        page_data = page_response.json()

        vacancy_count = page_data['total']
        if page >= vacancy_count / vacancy_count_per_page or page == 49:
            break

        for vacancy in page_data['objects']:
            yield vacancy, vacancy_count


def predict_salary(salary_from: Union[None, int],
        salary_to: Union[None, int]) -> Union[None, int]:
    """Return vacancy's approx salary."""
    if salary_from and salary_to:
        return int((salary_from + salary_to) / 2)
    elif salary_from:
        return int(salary_from * 1.2)
    elif salary_to:
        return int(salary_to * 0.8)
    return None


def predict_rub_salary_hh(currency: str, salary_from: int,
        salary_to: int) -> Union[None, int]:
    """Return vacancy's approx salary in rubles for hh.ru."""
    if currency == 'RUR':
        return predict_salary(salary_from, salary_to)
    return None


def predict_rub_salary_sj(currency: str, salary_from: int,
        salary_to: int) -> Union[int, None]:
    """Return vacancy's approx salary in rubles for superjob.ru."""
    if currency == 'rub':
        return predict_salary(salary_from, salary_to)
    return None


def get_hh_statistics(languages: list[str], hh_header: str,
        hh_professional_role_id: int, hh_specialization_id: int,
        hh_period: int, hh_per_page: int, hh_area_id: int) -> str:
    """
    Get statictics of vacancies and average salary for programming 
    language for hh.ru.
    """
    hh_statistics = []
    for language in languages:
        vacancies_processed = 0
        salaries_sum = 0
        for vacancy, vacancy_count in fetch_hh_vacancies(
            hh_header=hh_header,
            hh_professional_role_id=hh_professional_role_id,
            hh_specialization_id=hh_specialization_id,
            language=language,
            hh_per_page=hh_per_page,
            hh_area_id=hh_area_id,
            hh_period=hh_period):
            if vacancy is not None:
                vacancies_processed += 1
                salary = vacancy['salary']
                salaries_sum += predict_rub_salary_hh(
                    currency=salary['currency'],
                    salary_from=salary['from'],
                    salary_to=salary['to']
                )
        hh_statistics.append(
            [
                language,
                vacancy_count,
                vacancies_processed,
                int(salaries_sum / vacancies_processed)
            ]
        )
    return hh_statistics


def get_sj_statistics(languages: list[str], sj_catalogues_id: int,
        sj_key: str, vacancy_count_per_page: int, sj_town_id: int,
        sj_period: int) -> str:
    """
    Get statictics of vacancies and average salary for programming 
    language for superjob.ru.
    """
    sj_statistics = []
    for language in languages:
        vacancies_processed = 0
        salaries_sum = 0
        for vacancy, vacancy_count in fetch_sj_vacancies(
                language=language,
                sj_catalogues_id=sj_catalogues_id,
                sj_key=sj_key,
                vacancy_count_per_page=vacancy_count_per_page,
                sj_town_id=sj_town_id,
                sj_period=sj_period):
            if vacancy is not None:
                vacancies_processed += 1
                salaries_sum += predict_rub_salary_sj(
                    currency=vacancy['currency'],
                    salary_from=vacancy['payment_from'],
                    salary_to=vacancy['payment_to']
                )
        sj_statistics.append(
            [
                language,
                vacancy_count,
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
    hh_header = os.getenv('HH_HEADER')
    hh_table_name = 'HeadHunter Moscow'

    sj_key = os.getenv('SJ_KEY')
    sj_table_name = 'SuperJob Moscow'

    vacancy_count_per_page = 10

    programming_languages = [
        'JavaScript', 'Python', 'Java', 'C#', 'PHP', 'C++',
        'C', 'Ruby', 'Go'
    ]

    hh_statistics = get_hh_statistics(
        languages=programming_languages,
        hh_header=hh_header,
        hh_professional_role_id=96,
        hh_specialization_id=1,
        hh_period=30,
        vacancy_count_per_page=10,
        hh_area_id=1
    )
    sj_statistics = get_sj_statistics(
        languages=programming_languages,
        sj_catalogues_id=48,
        sj_key=sj_key,
        vacancy_count_per_page=vacancy_count_per_page,
        sj_town_id=4,
        sj_period=7
    )

    terminal_tables = (create_table(hh_table_name, hh_statistics),
                       create_table(sj_table_name, sj_statistics))
    print(*terminal_tables, sep='\n')


if __name__ == '__main__':
    main()
