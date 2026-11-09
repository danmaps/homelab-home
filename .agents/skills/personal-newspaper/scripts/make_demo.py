"""Rebuild the full fictional fixture. Does not collect sources or render a PDF."""
from copy import deepcopy
from datetime import date, timedelta
from pathlib import Path
import json

import newspaper as n
from onboarding import build_profile
from games import daily_chess, daily_sudoku


def demo():
    answers = n.load(n.ASSETS / 'setup.example.json')
    profile = build_profile(answers)
    profile['artwork']['mode'] = 'optional'
    profile['demo_note'] = 'The compact share sample illustrates comics/lessons; text-only section pages keep its download small. New users can require one image on every page.'
    snapshot = {'schema_version': 1, 'mode': 'demo', 'date': '2026-10-24', 'timezone': profile['timezone'], 'sources': {}}
    for source in profile['sources']:
        snapshot['sources'][source['id']] = {'status': 'demo', 'complete': False, 'observed_at': '2026-10-24T07:00:00+00:00',
            'method': 'demo', 'reason': 'Invented records for the portable template; no account was accessed.',
            'evidence': {'tool': 'synthetic_fixture', 'reference': 'full.snapshot.json', 'scope': source['scope']}, 'items': []}

    def item(source, key, title, summary, **fields):
        identity = source + ':' + key
        snapshot['sources'][source]['items'].append({'id': identity, 'title': title, 'summary': summary,
            'source_label': 'Fictional ' + source + ' records', **fields})
        return identity

    walk = item('calendar', 'walk', 'A river walk', 'A fictional walk at 10 a.m. on Saturday.', event_date='2026-10-24')
    library = item('calendar', 'library', 'An afternoon at the library', 'Fictional Sunday visit at 2 p.m.', event_date='2026-10-25')
    call = item('calendar', 'planning', 'Community garden planning', 'A fictional planning conversation next Tuesday.', event_date='2026-10-27')
    month = item('calendar', 'telescope', 'Telescope maintenance', 'A fictional equipment check on November 10.', event_date='2026-11-10')
    mail = item('mail', 'reply', 'A garden invitation needs a reply', 'A fictional invitation asks Morgan to choose a volunteer session.', person_id='morgan')
    later = item('mail', 'resolved', 'The old room request is closed', 'A later fictional confirmation closes the earlier room question.', person_id='morgan', action_status='completed')
    talk1 = item('mail', 'weekend', 'Choose a weekend activity', 'Morgan and Casey have two fictional options to discuss.')
    talk2 = item('mail', 'supplies', 'Decide what the garden needs', 'A fictional shared decision about using supplies already on hand.')
    lunch = item('shared', 'lunch', 'Monday lunch menu', 'Fictional published menu: vegetable pasta or a bean wrap.', kind='lunch')
    opportunity = item('shared', 'club', 'An optional astronomy club evening', 'A fictional club offers an observing session; no household registration is implied.', kind='opportunity')
    for person in ('morgan', 'jules'):
        item('tasks', person + '-scope', 'Exact TODO scope checked', 'Fictional complete list scope including undated and nested items.', kind='task_scope', person_id=person,
             lists=[person.title() + ' TODO'], all_open=True, undated=True, nested=True, scope_complete=True)
    task1 = item('tasks', 'jules-books', 'Pack the library books', 'An undated fictional open task.', kind='task', person_id='jules', state='open')
    task2 = item('tasks', 'jules-card', 'Put the library card in the bag', 'A fictional nested subtask.', kind='task', person_id='jules', state='open', parent_id=task1)
    adult_task = item('tasks', 'morgan-tools', 'Sort the garden tools', 'A fictional open personal task.', kind='task', person_id='morgan', state='open')
    item('school', 'term', 'School quarter 2', 'Fictional school-defined quarter dates.', kind='school_term', person_id='jules', term_id='Q2', start_date='2026-10-12', end_date='2026-12-18')
    item('school', 'grade-scope', 'Latest gradebooks checked', 'All fictional latest published course books were checked.', kind='grade_scope', person_id='jules', all_latest=True)
    grade1 = item('school', 'math', 'Mathematics grade', 'A fictional published course mark.', kind='grade', person_id='jules', course='Mathematics', mark='A-', percent='91%', term_id='Q2')
    grade2 = item('school', 'science', 'Science grade', 'A fictional published course mark.', kind='grade', person_id='jules', course='Science', mark='B+', percent='88%', term_id='Q2')
    assignment = item('school', 'sketch', 'Sketch a leaf', 'A fictional current-quarter unscored assignment.', kind='assignment', person_id='jules', term_id='Q2', due_date='2026-10-26', state='unscored')
    news1 = item('public', 'space', 'A small observatory opens its doors', 'An invented observatory story for the technology page.', content_scope='fictional')
    news2 = item('public', 'meeting', 'The town discusses a walking route', 'An invented public-affairs story for layout review.', content_scope='fictional')
    interest = item('public', 'animals', 'How animals stretch', 'Fictional animal-reading selection based on the example child interests.', person_id='jules', content_scope='fictional')
    clip = item('clips', 'training', 'A new training library', 'An invented organization reading selection.')
    notice1 = item('notices', 'survey', 'Staff survey', 'An invented new-message topic with a stated response window.')
    notice2 = item('notices', 'hours', 'Service desk hours', 'An older fictional notice that remains applicable.')
    announce = item('announcements', 'workshop', 'A public workshop', 'A fictional secondary newsletter announcement.')

    def article(headline, paragraphs, sources, fact, **fields):
        return {'headline': headline, 'paragraphs': paragraphs, 'source_ids': sources, 'fact_ids': [fact], **fields}

    pages = []
    for section in profile['sections']:
        page = {'id': section['id'], 'deck': 'A fictional example of the ' + section['title'].lower() + ' desk.', 'articles': []}
        pages.append(page)
        if section.get('window'):
            day = date(2026, 10, 24)
            start = day + timedelta(days=1) if section['window'] == 'tomorrow' else day
            end = start if section['window'] == 'tomorrow' else day + timedelta(days=6 if section['window'] == 'week' else 29)
            page.update(start_date=str(start), end_date=str(end))
    by_page = {p['id']: p for p in pages}
    by_page['today']['articles'] = [article('A little room for the river', ['The example household has a walk penciled in for 10 a.m. The calendar entry is invented for this sample.',
        'The newspaper brings the day into focus with readable summaries, dated plans and visible attribution. None of these example events should be treated as an invitation.'], [walk], 'walk')]
    by_page['today']['front_week'] = {'start_date': '2026-10-18', 'end_date': '2026-10-25', 'items': [
        {'event_date': '2026-10-24', 'title': 'A river walk', 'body': '10 a.m.; fictional.', 'source_ids': [walk]},
        {'event_date': '2026-10-25', 'title': 'Library afternoon', 'body': '2 p.m.; fictional.', 'source_ids': [library]}]}
    for key, identity, headline, when in [('tomorrow', library, 'An afternoon among the shelves', '2026-10-25'), ('week', call, 'A conversation about next season', '2026-10-27'), ('month', month, 'Keep an eye on the telescope', '2026-11-10')]:
        by_page[key]['articles'] = [article(headline, ['This invented calendar entry demonstrates a planning item inside the inclusive local date window.',
            'A live paper would check the actual event, cancellation state and preparation before describing it as a commitment.'], [identity], key, event_date=when, audience='general')]
    by_page['family-1']['articles'] = [article('At the shared table', ['The fictional Monday menu offers vegetable pasta or a bean wrap. Menu publication dates would remain visible in a live edition.',
        'Shared school information belongs on this family desk so it need not be repeated on every child page.'], [lunch], 'lunch')]
    by_page['family-2']['articles'] = [article('An evening with the stars', ['A fictional astronomy club offers an observing session. It is an opportunity, rather than a claim that someone has registered.',
        'A real edition would check the organizer, eligibility, dates and available places before describing the opportunity as current.'], [opportunity], 'club')]
    by_page['jules-1']['articles'] = [article('The latest published marks', ['These invented grade rows retain the exact course, mark, percentage and term from the fictional snapshot.'], [grade1, grade2], 'grades', grade_ids=[grade1, grade2]),
        article('Everything still on the TODO list', ['The example includes an undated item and its nested subtask. Nothing is completed or rescheduled by newspaper collection.'], [task1, task2], 'child-tasks', task_ids=[task1, task2])]
    by_page['jules-2']['articles'] = [article('In the current school quarter', ['The leaf sketch is unscored; that is distinct from missing, completed late or closed work. Previous-quarter assignments stay out of the paper.'], [assignment], 'assignments', assignment_ids=[assignment])]
    by_page['personal-1']['articles'] = [article('A reply and a small household task', ['The fictional invitation needs a choice of volunteer session. The open tool-sorting task remains separate from that reply.'], [mail, adult_task], 'adult-open', task_ids=[adult_task])]
    by_page['personal-2']['articles'] = [article('An older request is settled', ['A later fictional confirmation closes the old room question. The newspaper does not revive it as unfinished work.'], [later], 'adult-resolved', action_status='completed')]
    by_page['discussion-1']['articles'] = [article('Choose a shared afternoon', ['The two example adults have a weekend decision to make together. The discussion desk frames their choice without assigning an unagreed task.'], [talk1], 'discussion1', discussion_question='Would we enjoy a library visit or a garden afternoon?', decision_needed='Choose the activity and agree on a time together.')]
    by_page['discussion-2']['articles'] = [article('Start with what is already on hand', ['This fictional discussion concerns a shared garden plan and existing supplies. No spending figure or private financial record appears.'], [talk2], 'discussion2', discussion_question='Which supplies can we reuse for the garden?', decision_needed='Agree on the next small garden step.')]
    by_page['techmeme']['articles'] = [article('A view from the observatory', ['This invented item occupies the technology-publication desk. It is not a summary of the real publication.', 'In production, discovery indexes lead to the original reporting. A headline or video description alone cannot establish the contents of an unread article or unseen video.'], [news1], 'space')]
    by_page['memeorandum']['articles'] = [article('A route through the neighborhood', ['This invented public-affairs item demonstrates a second dedicated publication desk.', 'A live edition would retain the original publisher, reporting date and clear attribution for analysis or opinion.'], [news2], 'meeting')]
    by_page['organization']['articles'] = [article('A place to keep learning', ['An invented training library supplies the selective reading item. Mandatory notices take priority when this two-page pair needs more room.'], [clip], 'training'),
        article('Survey and continuing service hours', ['The fictional survey is a new topic. Service desk hours come from an older notice that still applies. Both topics receive their own source references.'], [notice1, notice2], 'notices')]
    by_page['industry']['articles'] = [article('A workshop worth keeping on the list', ['A smaller fictional newsletter announcement remains visible alongside the main stories. The all-topics check prevents a collected secondary topic from disappearing.'], [announce], 'workshop')]
    prompts = n.load(n.ASSETS / 'demo-art/prompts.json')
    prompt_map = {x['key']: x['prompt'] for x in prompts['prompts']}

    def image(key, alt):
        return {'path': 'demo-art/' + key + '.png', 'alt': alt, 'origin': 'generated', 'generated_for_date': '2026-10-24',
                'generation_evidence': {'tool': 'built-in image_gen', 'reference': 'demo-art/prompts.json#' + key, 'prompt': prompt_map[key]}}
    by_page['jules-1']['image'] = image('comic', 'A fictional child measures a seedling while a cat raises a much taller tail.')
    by_page['jules-1']['comic'] = {'premise': 'The cat has its own idea of impressive plant growth.', 'cast_ids': ['jules'], 'reference_ids': ['fictional-child-reference'],
        'captions': ['A promising start.', 'Time to measure the progress.', 'The competition is growing.']}
    by_page['jules-2']['image'] = image('lesson', 'Four numbered stages for a seated beagle and four for a stretching cat.')
    by_page['jules-2']['drawing_lesson'] = {'subjects': [
        {'species': 'dog', 'breed': 'Beagle', 'pose': 'Seated, three-quarter view', 'illustrated_step_count': 4,
         'steps': ['Sketch two circles for the head and chest.', 'Add a seated body oval and front-leg guides.', 'Draw floppy ears, muzzle, paws and a curled tail.', 'Finish the face, outline and grayscale markings.']},
        {'species': 'cat', 'breed': 'Domestic shorthair', 'pose': 'Stretching, side view', 'illustrated_step_count': 4,
         'steps': ['Sketch a head circle and a long body oval.', 'Add extended front legs and raised hindquarters.', 'Draw triangular ears, a curved tail, paws and face.', 'Finish the outline and grayscale fur markings.']}]}
    by_page['games-1']['image'] = image('back', 'A fictional adult reaches for tea and receives a tennis ball from an eager dog.')
    by_page['games-1']['comic'] = {'premise': 'The dog schedules a ball break before the tea break.', 'cast_ids': ['morgan'], 'reference_ids': [],
        'captions': ['Time for a quiet cup.', 'A different refreshment request.', 'Tea can wait one throw.']}
    across = [(1,'HEART','What the gardener puts into the beds'), (6,'EMBER','Campfire glow, remembered by the camper'), (7,'ABUSE','What the household\'s kind humor avoids'), (8,'RESIN','Sticky stuff in a nature notebook'), (9,'TREND','A tech reader watches this direction')]
    down = [(1,'HEART','Organ that pumps blood'), (2,'EMBER','Glowing remnant of a fire'), (3,'ABUSE','Mistreat'), (4,'RESIN','Sticky plant secretion'), (5,'TREND','General direction of change')]
    crossword = {'grid': ['HEART','EMBER','ABUSE','RESIN','TREND'], 'clues': [
        {'direction': direction, 'number': number, 'answer': answer, 'clue': clue, 'personalized': direction=='across',
         'personal_context': 'Fictional household interests in gardening, nature and technology.' if direction=='across' else ''}
        for direction, values in [('across', across), ('down', down)] for number, answer, clue in values]}
    jumble = {'intro': 'Unscramble the four words, then rearrange the circled letters for the bonus.', 'words': [
        {'answer':'PANEL','scrambled':'LPANE','circles':[0]}, {'answer':'AGENT','scrambled':'TNEAG','circles':[0]},
        {'answer':'PAPER','scrambled':'RPAPE','circles':[0]}, {'answer':'READER','scrambled':'EDARER','circles':[1,0]}],
        'bonus':'PAPER','bonus_clue':'The morning edition.'}
    edition = {'schema_version': 1, 'mode': 'demo', 'title': profile['title'], 'date': '2026-10-24', 'timezone': profile['timezone'],
               'as_of': '2026-10-24T07:15:00+00:00', 'pages': pages,
               'puzzles': {'crossword': crossword, 'jumble': jumble, 'sudoku': daily_sudoku('2026-10-24'), 'chess': daily_chess('2026-10-24')}}
    return profile, snapshot, edition


if __name__ == '__main__':
    for name, obj in zip(('profile','snapshot','edition'), demo()):
        n.save(n.ASSETS / ('full.' + name + '.json'), obj)
    print('Rebuilt the full fictional profile, snapshot and edition.')
