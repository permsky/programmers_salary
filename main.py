import os
import sys
from itertools import count
from typing import Union, Generator

import requests
from dotenv import load_dotenv
from loguru import logger
from terminaltables import AsciiTable


logger.add(
    sys.stderr,
    format='[{time:HH:mm:ss}] <lvl>{message}</lvl>',
    level='ERROR'
)


def fetch_hh_vacancies(
        header: str,
        professional_role_id: int,
        specialization_id: int,
        language: str,
        vacancy_count_per_page: int,
        area_id: int,
        period: int) -> Generator[tuple[dict, int], None, None]:
    """Create generator of vacancies from hh.ru"""
    with requests.Session() as s:
        s.headers.update({'User-Agent': header})
        s.params = {
            'period': period,
            'specialization': specialization_id,
            'area': area_id,
            'professional_role': professional_role_id,
            'per_page': vacancy_count_per_page,
            'text': language,
        }
        for page in count():
            page_response = s.get(
                url='https://api.hh.ru/vacancies',
                params={'page': page}
            )
            page_response.raise_for_status()
            page_content = page_response.json()

            for vacancy in page_content['items']:
                yield vacancy, page_content['found']

            if page >= page_content['pages'] - 1:
                break


def fetch_sj_vacancies(
        language: str,
        catalogues_id: int,
        token: str,
        vacancy_count_per_page: int,
        town_id: int,
        period: int) -> Generator[tuple[dict, int], None, None]:
    """Create generator of vacancies from superjob.ru"""
    with requests.Session() as s:
        s.headers.update({'X-Api-App-Id': token})
        s.params = {
            'town': town_id,
            'catalogues': catalogues_id,
            'count': vacancy_count_per_page,
            'period': period,
            'keyword': language,
        }
        for page in count():
            page_response = s.get(
                url='https://api.superjob.ru/2.0/vacancies',
                params={'page': page}
            )
            page_response.raise_for_status()
            page_content = page_response.json()

            for vacancy in page_content['objects']:
                yield vacancy, page_content['total']

            if not page_content['more']:
                break


def predict_salary(
        salary_from: Union[None, int],
        salary_to: Union[None, int]) -> Union[None, int]:
    """Return vacancy's approx salary."""
    if salary_from and salary_to:
        return int((salary_from + salary_to) / 2)
    elif salary_from:
        return int(salary_from * 1.2)
    elif salary_to:
        return int(salary_to * 0.8)
    return None


def predict_rub_salary_hh(vacancy: dict) -> Union[None, int]:
    """Return vacancy's approx salary in rubles for hh.ru."""
    salary = vacancy['salary']
    if salary and salary['currency'] == 'RUR':
        return predict_salary(salary['from'], salary['to'])
    return None


def predict_rub_salary_sj(vacancy: dict) -> Union[int, None]:
    """Return vacancy's approx salary in rubles for superjob.ru."""
    if vacancy['currency'] == 'rub':
        return predict_salary(vacancy['payment_from'], vacancy['payment_to'])
    return None


def get_hh_statistics(
        languages: list[str],
        header: str,
        professional_role_id: int,
        specialization_id: int,
        period: int,
        vacancy_count_per_page: int,
        area_id: int) -> str:
    """
    Get statictics of vacancies and average salary for programming
    language for hh.ru.
    """
    language_statistics = []
    for language in languages:
        vacancies_processed = 0
        salaries_sum = 0
        for vacancy, vacancy_count in fetch_hh_vacancies(
                header=header,
                professional_role_id=professional_role_id,
                specialization_id=specialization_id,
                language=language,
                vacancy_count_per_page=vacancy_count_per_page,
                area_id=area_id,
                period=period):
            if vacancy:
                approximate_rub_salary = predict_rub_salary_hh(vacancy)
                if approximate_rub_salary:
                    vacancies_processed += 1
                    salaries_sum += approximate_rub_salary
        average_rub_salary = salaries_sum / vacancies_processed
        language_statistics.append(
            [
                language,
                vacancy_count,
                vacancies_processed,
                int(average_rub_salary if vacancies_processed else 0)
            ]
        )
    return language_statistics


def get_sj_statistics(
        languages: list[str],
        catalogues_id: int,
        token: str,
        vacancy_count_per_page: int,
        town_id: int,
        period: int) -> str:
    """
    Get statictics of vacancies and average salary for programming
    language for superjob.ru.
    """
    language_statistics = []
    for language in languages:
        vacancies_processed = 0
        salaries_sum = 0
        for vacancy, vacancy_count in fetch_sj_vacancies(
                language=language,
                catalogues_id=catalogues_id,
                token=token,
                vacancy_count_per_page=vacancy_count_per_page,
                town_id=town_id,
                period=period):
            if vacancy:
                approximate_rub_salary = predict_rub_salary_sj(vacancy)
                if approximate_rub_salary:
                    vacancies_processed += 1
                    salaries_sum += approximate_rub_salary
        average_rub_salary = salaries_sum / vacancies_processed
        language_statistics.append(
            [
                language,
                vacancy_count,
                vacancies_processed,
                int(average_rub_salary if vacancies_processed else 0)
            ]
        )
    return language_statistics


def create_table(table_name: str, table_content: list) -> str:
    """Create terminal table."""
    table_header = [
        [
            'Язык программирования',
            'Вакансий найдено',
            'Вакансий обработано',
            'Средняя зарплата'
        ]
    ]
    table_header.extend(table_content)
    table = AsciiTable(table_header, table_name)
    return table.table


@logger.catch
def main() -> None:
    """Print average salary tables for hh.ru and superjob.ru."""
    load_dotenv()
    header = os.getenv('HH_HEADER')
    hh_table_name = 'HeadHunter Moscow'

    token = os.getenv('SJ_TOKEN')
    sj_table_name = 'SuperJob Moscow'

    vacancy_count_per_page = 10

    programming_languages = [
        'JavaScript', 'Python', 'Java', 'C#', 'PHP', 'C++',
        'C', 'Ruby', 'Go'
    ]

    try:
        hh_statistics = get_hh_statistics(
            languages=programming_languages,
            header=header,
            professional_role_id=96,
            specialization_id=1,
            period=30,
            vacancy_count_per_page=vacancy_count_per_page,
            area_id=1
        )
        sj_statistics = get_sj_statistics(
            languages=programming_languages,
            catalogues_id=48,
            token=token,
            vacancy_count_per_page=vacancy_count_per_page,
            town_id=4,
            period=7
        )
    except requests.exceptions.HTTPError:
        logger.error(
            'Ошибка обработки HTTP запроса, попробуйте перезапустить скрипт'
        )
        sys.exit(1)

    terminal_tables = (create_table(hh_table_name, hh_statistics),
                       create_table(sj_table_name, sj_statistics))
    print(*terminal_tables, sep='\n')


if __name__ == '__main__':
    main()
