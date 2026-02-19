import json
import re
from collections import defaultdict
from collections.abc import Mapping, MutableSequence, Sequence
from os import PathLike
from pathlib import Path
from typing import TypedDict, cast

import inquirer


class UserCancel(Exception): pass


class MediaEntry(TypedDict):
    title: str
    series: str
    series_sort: int
    # year_experienced: int | None
    title_override: str | None


def add_entry(
    json_data: Mapping[str, MutableSequence[MediaEntry]],
    include_title_override: bool = False,
) -> None:
    categories = list(json_data.keys())
    questions = [
        inquirer.List(
            name='category',
            message="Category",
            choices=categories,
        ),
        inquirer.Text(
            name='title',
            message='Title'
        ),
        # inquirer.Text(
        #     name='year_experienced',
        #     message='Year Experienced',
        #     validate=lambda _, x: re.match(r'^$|\d{4}', x)
        # )
    ]
    if include_title_override:
        questions.append(
            inquirer.Text(
                name='title_override',
                message='Title Override',
            ),
        )
    answers = inquirer.prompt(questions)
    if answers is None:
        raise UserCancel
    answers = cast(dict[str, str], answers)
    category = answers['category'].strip()
    title = answers['title'].strip()
    # year_experienced_raw = answers['year_experienced'].strip()
    # year_experienced = (int(year_experienced_raw)
    #                     if year_experienced_raw else None)
    title_override = answers.get('title_override', '').strip() or None
    existing_category = json_data[category]

    if any(
        entry['title'] == title
        for entry in existing_category
    ):
        print('Already exists.')
        return

    existing_franchises = {series_name for entry in existing_category
                           if (series_name := entry['series']) is not None}
    series_regex = re.compile(r'^([^\\(]+)')
    possible_franchises = [
        series_name for series_name in existing_franchises
        if (reg_match := re.match(series_regex, series_name)) is not None
        if reg_match.group(0) in title
    ]
    series_temp = None
    if possible_franchises:
        series_options = possible_franchises + ['NONE', 'CUSTOM']
        questions = [
            inquirer.List(
                name='series',
                message="Series",
                choices=series_options,
            ),
        ]
        answers = inquirer.prompt(questions)
        if answers is None:
            raise UserCancel
        series_temp = answers['series']
        if series_temp == 'NONE':
            series_temp = title
        elif series_temp == 'CUSTOM':
            series_temp = None
    if series_temp is None:
        questions = [
            inquirer.Text(
                name='series',
                message='Series',
            ),
        ]
        answers = inquirer.prompt(questions)
        if answers is None:
            raise UserCancel
        series_temp = answers['series'] or title

    series = series_temp

    series_sort = 0
    if series:
        existing_series = [entry for entry in existing_category
                           if entry['series'] == series]
        existing_series.sort(key=lambda d: d['series_sort'])
        if existing_series:
            title_to_entry_map = {entry['title']: entry
                                  for entry in existing_series}
            series_titles = list(title_to_entry_map.keys())
            options = ['At the start', 'At the end'] + series_titles
            questions = [
                inquirer.List(
                    name='placement',
                    message='Where should it go after?',
                    choices=options,
                )
            ]
            series_answer = inquirer.prompt(questions)
            if series_answer is None:
                raise UserCancel
            placement = series_answer['placement']
            if placement == 'At the start':
                series_titles.insert(0, title)
            elif placement == 'At the end':
                series_titles.append(title)
            else:
                placement_index = series_titles.index(placement)
                placement_index += 1
                series_titles.insert(placement_index, title)

            for i, entry_title in enumerate(series_titles):
                entry = title_to_entry_map.get(entry_title)
                if entry is None:
                    series_sort = i
                else:
                    entry['series_sort'] = i

    new_entry = MediaEntry(
        title=title,
        series=series,
        series_sort=series_sort,
        # year_experienced=year_experienced,
        title_override=title_override,
    )
    json_data[category].append(new_entry)


def create_markdown(
    json_data: Mapping[str, Sequence[MediaEntry]],
    export_path: PathLike | str = 'all_media.md',
) -> None:

    def title_to_sort_by(group: list[MediaEntry]) -> str:
        group.sort(key=lambda d: d['series_sort'])
        title = group[0].get('series') or group[0]['title']
        if title.startswith(('The ', 'A ', 'An ')):
            article, rest = title.split(' ', 1)
            title = f'{rest}, {article}'
        return title.casefold()

    category_titles = defaultdict[str, list[str]](list)
    for category, entries in json_data.items():
        series_groups: dict[str, list[MediaEntry]] = {}
        for entry in entries:
            series_groups.setdefault(entry['series'], []).append(entry)
        sorted_series = sorted(
            series_groups.values(),
            key=title_to_sort_by
        )
        for group in sorted_series:
            for entry in group:
                title_to_use = entry.get('title_override') or entry['title']
                if title_to_use.startswith(('The ', 'A ', 'An ')):
                    article, rest = title_to_use.split(' ', 1)
                    title_to_use = f'{rest}, {article}'
                category_titles[category].append(title_to_use)

    with open(export_path, mode='w', encoding='utf8') as f:
        f.write('# All Media\n\n')
        for category, title_list in category_titles.items():
            f.write(f'## {category}\n')
            for title in title_list:
                f.write(f'- {title}\n')
            f.write('\n')


def main():
    raw_file = Path('all_media_raw.json')
    with raw_file.open(mode='r', encoding='utf8') as f:
        existing_json: dict[str, list[MediaEntry]] = json.load(f)
    try:
        while True:
            add_entry(existing_json)
            res = input('Done! Add another? (Y/n): ')
            if res.casefold() == 'n':
                break
    except UserCancel:
        res = input('Save unsaved work? (Y/n): ')
        if res.casefold() == 'n':
            return
    export_path = r'C:\Users\tomas\My Drive\Personal\Documents\All Media.md'
    create_markdown(existing_json, export_path=export_path)
    with raw_file.open(mode='w', encoding='utf-8') as f:
        json.dump(existing_json, f, indent=4)
    print('Saved!')


if __name__ == '__main__':
    main()
