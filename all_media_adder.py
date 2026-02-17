import json
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import TypedDict, cast

import inquirer


class UserCancel(Exception): pass


class MediaEntry(TypedDict):
    title: str
    series: str
    series_sort: int
    year_experienced: int | None
    title_override: str | None


def add_entry(
    json_data: dict[str, list[MediaEntry]],
    include_title_override: bool = False,
):
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
        #     name='series',
        #     message='Series'
        # ),
        inquirer.Text(
            name='year_experienced',
            message='Year Experienced',
            validate=lambda _, x: re.match(r'^$|\d{4}', x) 
        )
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
    year_experienced_raw = answers['year_experienced'].strip()
    year_experienced = (int(year_experienced_raw)
                        if year_experienced_raw else None)
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
    possible_franchises = [series_name for series_name in existing_franchises
                           if series_name in title]
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

    # TODO: Show warning if title or series exists in different category

    placement_index = 0
    if series:
        existing_series = [entry for entry in existing_category
                           if entry['series'] == series]
        existing_series.sort(key=lambda d: d['series_sort'])
        if existing_series:
            series_titles = [entry['title'] for entry in existing_series]
            options = ['At the start'] + series_titles
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
            placement_index = options.index(placement)
            for entry in existing_series:
                if entry['series_sort'] >= placement_index:
                    entry['series_sort'] += 1
    new_entry = MediaEntry(
        title=title,
        series=series,
        series_sort=placement_index,
        year_experienced=year_experienced,
        title_override=title_override,
        
    )
    json_data[category].append(new_entry)


def create_markdown(json_data: Mapping[str, Sequence[MediaEntry]]) -> None:
    """
    Create a Markdown file in this format:
    
    # All Media

    ## [category name]
    - Entry title
    ...

    ## [category name 2]
    ...

    Within each category, items should be sorted alphabetically
    Items that start with "The", "A", or "An" should be reformatted
    so that the article is at the end.
    For example, "The Legend of Zelda: Breath of the Wild" should be
    formatted and sorted as "Legend of Zelda: Breath of the Wild, The".
    However, if "title_override" is provided, use that directly.

    Series should be grouped together, ignoring alphabetical sort.
    Within each series, use series_sort instead. Within the overall
    list, the series should be sorted at the alphabetical location
    of the title of the entry with the smallest series_sort (usually 0).
    """
    with open('all_media.md', mode='w', encoding='utf8') as f:
        f.write('# All Media\n\n')
        for category, entries in json_data.items():
            f.write(f'## {category}\n')
            series_groups: dict[str, list[MediaEntry]] = {}
            for entry in entries:
                series_groups.setdefault(entry['series'], []).append(entry)
            title_to_sort_by = lambda group: group[0].get('title_override') or group[0]['title']
            sorted_series = sorted(
                series_groups.values(),
                key=title_to_sort_by
            )
            for group in sorted_series:
                group.sort(key=lambda d: d['series_sort'])
                for entry in group:
                    title_to_use = entry.get('title_override') or entry['title']
                    if title_to_use.startswith(('The ', 'A ', 'An ')):
                        article, rest = title_to_use.split(' ', 1)
                        title_to_use = f'{rest}, {article}'
                    f.write(f'- {title_to_use}\n')
            f.write('\n')
    

def main():
    raw_file = Path('all_media_raw.json')
    with raw_file.open(mode='r', encoding='utf8') as f:
        existing_json: dict[str, list[MediaEntry]] = json.load(f)
    try:
        while True:
            add_entry(existing_json)
            res = input('Done! Add another? (y/n): ')
            if res.casefold() != 'y':
                break    
        create_markdown(existing_json)
        with raw_file.open(mode='w', encoding='utf-8') as f:
            json.dump(existing_json, f, indent=4)
        print('Saved!')
    except UserCancel:
        return


if __name__ == '__main__':
    main()
