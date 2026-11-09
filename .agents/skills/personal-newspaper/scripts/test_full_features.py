"""Full-feature behavior checks with fictional inputs and isolated mocked operations."""
from copy import deepcopy
from datetime import datetime
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

import newspaper as n
import operations as ops
from features import check_novelty
from games import validate_chess, validate_crossword, validate_jumble, validate_sudoku
from onboarding import build_profile
import sources


class FullFeatureTests(unittest.TestCase):
    def setUp(self):
        self.profile = n.load(n.ASSETS / 'full.profile.json')
        self.snapshot = n.load(n.ASSETS / 'full.snapshot.json')
        self.edition = n.load(n.ASSETS / 'full.edition.json')
        self.pages = {p['id']: p for p in self.edition['pages']}

    def check(self):
        return n.validate(self.profile, self.snapshot, self.edition, n.ASSETS)

    def test_full_fixture_covers_every_module(self):
        result = self.check()
        self.assertEqual(result['intended_pages'], 18)
        self.assertFalse(result['feature_gaps'])
        self.assertEqual(set(result['games']), {'crossword','jumble','sudoku','chess'})

    def test_missing_nested_subtask_cannot_hide_in_citations(self):
        self.pages['jules-1']['articles'][1]['task_ids'].pop()
        with self.assertRaisesRegex(ValueError, 'Every open TODO'):
            self.check()

    def test_missing_latest_grade_row_is_rejected(self):
        self.pages['jules-1']['articles'][0]['grade_ids'].pop()
        with self.assertRaisesRegex(ValueError, 'Every latest published grade'):
            self.check()

    def test_previous_quarter_assignment_is_rejected_everywhere(self):
        assignment = next(i for i in self.snapshot['sources']['school']['items'] if i.get('kind') == 'assignment')
        assignment['term_id'] = 'Q1'
        with self.assertRaisesRegex(ValueError, 'Previous-term'):
            self.check()

    def test_previous_quarter_todo_overlap_does_not_revive_work(self):
        old = {'id':'school:old', 'title':'Prior quarter work', 'summary':'Fictional prior-term assignment', 'source_label':'Fictional school',
               'kind':'assignment', 'person_id':'jules', 'term_id':'Q1', 'state':'missing'}
        self.snapshot['sources']['school']['items'].append(old)
        task = next(i for i in self.snapshot['sources']['tasks']['items'] if i['id']=='tasks:jules-books')
        task['assignment_id']='school:old'
        with self.assertRaisesRegex(ValueError, 'TODO must not revive'):
            self.check()

    def test_future_dated_missing_current_term_stays_required(self):
        assignment = next(i for i in self.snapshot['sources']['school']['items'] if i.get('kind') == 'assignment')
        assignment.update(due_date='2027-01-10', state='missing')
        self.assertTrue(self.check()['passed'])
        self.pages['jules-2']['articles'][0]['assignment_ids']=[]
        with self.assertRaisesRegex(ValueError, 'Current-term'):
            self.check()

    def test_unknown_term_requires_visible_gap_and_excludes_assignments(self):
        self.snapshot['sources']['school']['items'] = [i for i in self.snapshot['sources']['school']['items'] if i.get('kind')!='school_term']
        article=self.pages['jules-2']['articles'][0]
        article.update(assignment_ids=[], source_ids=['school:math'])
        with self.assertRaisesRegex(ValueError, 'explicit assignments coverage note'):
            self.check()
        self.pages['jules-2']['coverage_notes']=[{'module':'assignments','status':'unavailable','reason':'The school term could not be verified.'}]
        result=self.check()
        self.assertFalse(result['coverage']['complete'])
        self.assertEqual(result['feature_gaps'][0]['module'],'assignments')

    def test_wrong_person_record_is_rejected(self):
        task = next(i for i in self.snapshot['sources']['tasks']['items'] if i['id']=='tasks:jules-card')
        task['person_id']='morgan'
        with self.assertRaisesRegex(ValueError, 'matching person|another person'):
            self.check()

    def test_shared_lunch_cannot_repeat_on_child_page(self):
        self.pages['jules-1']['articles'][0]['source_ids'].append('shared:lunch')
        with self.assertRaisesRegex(ValueError, 'Shared school/lunch'):
            self.check()

    def test_discussion_requires_question_and_joint_decision(self):
        self.pages['discussion-1']['articles'][0].pop('discussion_question')
        with self.assertRaisesRegex(ValueError, 'shared question and decision'):
            self.check()

    def test_child_planning_needs_real_parent_action(self):
        article=self.pages['week']['articles'][0]
        article['source_ids']=['tasks:jules-card']
        with self.assertRaisesRegex(ValueError, 'real parent action'):
            self.check()
        article.update(audience='parent_action',parent_action='Coordinate the library transport with the other adult.')
        self.assertTrue(self.check()['passed'])

    def test_completed_request_cannot_be_reopened_in_copy(self):
        self.pages['personal-2']['articles'][0].pop('action_status')
        with self.assertRaisesRegex(ValueError, 'completed request'):
            self.check()

    def test_secondary_notice_on_required_pair_is_mandatory(self):
        self.pages['organization']['articles'][1]['source_ids'].remove('notices:hours')
        with self.assertRaisesRegex(ValueError, 'Mandatory topic missing'):
            self.check()

    def test_requested_comic_and_likeness_reference_are_required(self):
        self.pages['jules-1']['comic']['reference_ids']=[]
        with self.assertRaisesRegex(ValueError,'character references'):
            self.check()
        self.pages['jules-1'].pop('comic')
        with self.assertRaisesRegex(ValueError,'personalized comic'):
            self.check()

    def test_lesson_stage_counts_and_different_poses_are_required(self):
        lesson=self.pages['jules-2']['drawing_lesson']['subjects']
        lesson[0]['illustrated_step_count']=3
        with self.assertRaisesRegex(ValueError,'stage counts'):
            self.check()
        lesson[0]['illustrated_step_count']=4
        lesson[1]['pose']=lesson[0]['pose']
        with self.assertRaisesRegex(ValueError,'different poses'):
            self.check()

    def test_full_width_art_mode_requires_every_page_image(self):
        self.profile['artwork']['mode']='one_per_page'
        with self.assertRaisesRegex(ValueError,'Missing full-width image'):
            self.check()

    def test_crossword_bad_crossings_and_personalization_fail(self):
        puzzle=deepcopy(self.edition['puzzles']['crossword'])
        puzzle['grid'][0]='X' + puzzle['grid'][0][1:]
        with self.assertRaisesRegex(ValueError,'disagree'):
            validate_crossword(puzzle)
        puzzle=deepcopy(self.edition['puzzles']['crossword'])
        with self.assertRaisesRegex(ValueError,'configured fraction'):
            validate_crossword(puzzle,1)

    def test_invalid_jumble_extraction_is_rejected(self):
        self.edition['puzzles']['jumble']['bonus']='NEWS'
        with self.assertRaisesRegex(ValueError,'bonus'):
            self.check()

    def test_nonunique_sudoku_is_rejected(self):
        self.edition['puzzles']['sudoku']['grid']=['000000000']*9
        with self.assertRaisesRegex(ValueError,'exactly one solution'):
            self.check()

    def test_multiple_legal_chess_mates_are_rejected(self):
        with self.assertRaisesRegex(ValueError,'exactly one legal solution'):
            validate_chess({'fen':'7k/5K2/8/6Q1/8/8/8/8 w - - 0 1','solution_uci':'g5h5'})

    def test_daily_art_and_premise_reuse_are_rejected(self):
        record={'date':'2026-10-24','mode':'live','artwork_sha256':['same'],'premises':[], 'urls':[], 'issue_ids':[], 'lessons':[]}
        old={**record,'date':'2026-10-23'}
        with self.assertRaisesRegex(ValueError,'Daily artwork'):
            check_novelty(record,{'editions':[old]},{'mode':'live'})
        old['artwork_sha256']=[]
        record['premises']=old['premises']=['Same joke']
        with self.assertRaisesRegex(ValueError,'premise repeats'):
            check_novelty(record,{'editions':[old]},{'mode':'live'})

    def test_revisited_story_and_breed_need_reasons(self):
        record={'date':'2026-10-24','mode':'live','artwork_sha256':[],'premises':[], 'urls':['https://example.org/story'], 'issue_ids':[], 'lessons':[]}
        old={**record,'date':'2026-10-23'}
        with self.assertRaisesRegex(ValueError,'Revisited stories'):
            check_novelty(record,{'editions':[old]},{'mode':'live'})
        check_novelty(record,{'editions':[old]},{'mode':'live','revisit_reasons':{'https://example.org/story':'The organizer published a new date.'}})

    def test_credentials_in_comic_captions_are_rejected(self):
        self.pages['jules-1']['comic']['captions'][0]='ghp_' + 'x'*25
        with self.assertRaisesRegex(ValueError,'privacy'):
            self.check()

    def test_unconfirmed_setup_and_unreviewed_examples_are_blocked(self):
        answers=n.load(n.ASSETS/'setup.example.json')
        answers['confirmed']=False
        with self.assertRaisesRegex(ValueError,'confirmed'):
            build_profile(answers)
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(ValueError,'fictional'):
                ops.configure(temporary,n.load(n.ASSETS/'setup.example.json'))

    def test_solo_profile_can_omit_family_and_games(self):
        answers=n.load(n.ASSETS/'setup.example.json')
        answers.update(members=[],owner_id=None,discussion_person_id=None,family_desk=False,artwork={'mode':'none'},games={'enabled':[],'pages':1})
        profile=build_profile(answers)
        self.assertFalse(any(s['kind'] in {'family','child','personal','discussion','games'} for s in profile['sections']))


class OperationsTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        answers=n.load(n.ASSETS/'setup.example.json')
        answers.pop('example_only')
        ops.configure(self.root,answers)
        self.profile=n.load(self.root/'.local/profile.json')
        self.folder=self.root/'outputs/2026-10-24-r001'
        self.folder.mkdir()
        (self.folder/'newspaper.pdf').write_bytes(b'isolated checked PDF bytes for workflow unit tests')
        self.at=datetime.fromisoformat('2026-10-24T07:15:00+00:00')
        self.receipt={'edition_id':'2026-10-24-r001','date':'2026-10-24','mode':'live','created_at':'2026-10-24T07:00:00+00:00',
            'pdf_sha256':n.sha256(self.folder/'newspaper.pdf'),'input_sha256':{},'qa_passed':True,'visual_review':True,
            'delivery':{'status':'local_ready'},'printing':{'status':'not_requested'},'coverage':{'complete':True},
            'novelty':{'date':'2026-10-24','mode':'live','urls':[],'issue_ids':[],'premises':[],'lessons':[],'artwork_sha256':[]}}
        n.save(self.folder/'receipt.json',self.receipt)
        n.save(self.folder/'qa.json',{'passed':True,'visual_review':True})
        self.snapshot=n.load(n.ASSETS/'full.snapshot.json')
        self.snapshot['mode']='live'
        for source in self.snapshot['sources'].values():
            source.update(status='current',complete=True,method='connector')
        n.save(self.folder/'snapshot.json',self.snapshot)

    def email(self):
        self.profile['delivery']={'channel':'email','recipients':['new-user@example.org'],'authorization':'Fictional unit-test authorization'}
        attachment=self.root/'readback.pdf'
        attachment.write_bytes((self.folder/'newspaper.pdf').read_bytes())
        return {'status':'sent','edition_id':self.receipt['edition_id'],'provider':'mock','to':['new-user@example.org'], 'message_id':'sent-42', 'sent_at':'2026-10-24T07:05:00+00:00',
                'attachment':{'readback_path':str(attachment),'sha256':self.receipt['pdf_sha256']},
                'verification':{'method':'sent_message_readback','tool':'mock','reference':'mock-sent-42','message_id':'sent-42','to':['new-user@example.org'],
                                'attachment_sha256':self.receipt['pdf_sha256'],'verified_at':'2026-10-24T07:06:00+00:00'}}

    def printable(self):
        self.profile['printing'].update(enabled=True,test_passed=True,physical_output_verified=True,printer='Test_Queue',test_printer='Test_Queue')
        n.save(self.root/'.local/profile.json',self.profile)

    def test_setup_keeps_requested_automation_and_printing_inactive(self):
        self.assertFalse(self.profile['printing']['enabled'])
        self.assertFalse(self.profile['schedule']['enabled'])

    def test_valid_email_requires_actual_attachment_readback_bytes(self):
        email=self.email()
        ops.validate_email(email,self.receipt,self.profile,self.at)
        Path(email['attachment']['readback_path']).write_bytes(b'different')
        with self.assertRaisesRegex(ValueError,'actual bytes'):
            ops.validate_email(email,self.receipt,self.profile,self.at)

    def test_outbox_wrong_recipient_and_extra_recipient_fail(self):
        for mutation in ({'status':'queued'},{'to':['wrong@example.org']},{'cc':['extra@example.org']}):
            email=self.email()
            email.update(mutation)
            with self.assertRaises(ValueError):
                ops.validate_email(email,self.receipt,self.profile,self.at)

    def test_local_handoff_records_history_without_claiming_email(self):
        result=ops.record_local(self.root,self.folder)
        self.assertEqual(result['status'],'local_ready')
        self.assertEqual(n.load(self.root/'.local/edition-history.json')['editions'][0]['delivery']['status'],'local_ready')

    def test_live_state_resumes_checked_pending_email(self):
        self.profile['delivery']={'channel':'email','recipients':['new-user@example.org'],'authorization':'Unit-test fixture'}
        n.save(self.root/'.local/profile.json',self.profile)
        self.receipt['delivery']['status']='email_delivery_pending'
        n.save(self.folder/'receipt.json',self.receipt)
        result=ops.state(self.root,'2026-10-24')
        self.assertEqual(result['stage'],'email_delivery_pending')
        self.assertTrue(result['latest']['pdf_intact'])

    def test_printing_requires_a_physically_confirmed_pinned_queue(self):
        with self.assertRaisesRegex(ValueError,'physically confirm'):
            ops.printing_preference(self.root,True)
        self.printable()
        self.profile['printing']['printer']='Changed_Queue'
        self.assertIn('own physical test',ops.print_gate(self.profile,self.receipt,self.snapshot,self.at))

    def test_stale_incomplete_and_late_prints_are_skipped(self):
        self.printable()
        self.snapshot['sources']['calendar']['complete']=False
        self.assertIn('incomplete',ops.print_gate(self.profile,self.receipt,self.snapshot,self.at))
        self.snapshot['sources']['calendar']['complete']=True
        self.snapshot['sources']['calendar']['observed_at']='2026-10-23T07:00:00+00:00'
        self.assertIn('stale',ops.print_gate(self.profile,self.receipt,self.snapshot,self.at))
        for source in self.snapshot['sources'].values():
            source['observed_at']='2026-10-24T07:10:00+00:00'
        self.assertIn('deadline',ops.print_gate(self.profile,self.receipt,self.snapshot,self.at,True))

    def test_ambiguous_print_is_not_retried_across_revisions(self):
        self.printable()
        calls=[]
        def runner(args,**kwargs):
            calls.append(args)
            return SimpleNamespace(returncode=0,stdout='unknown response' if args[0]=='lp' else 'printer enabled',stderr='')
        first=ops.submit_print(self.root,self.folder,runner=runner,at=self.at)
        self.assertEqual(first['status'],'unverified')
        second=ops.submit_print(self.root,self.folder,runner=runner,at=self.at)
        self.assertTrue(second['duplicate_skipped'])
        self.assertEqual(len([a for a in calls if a[0]=='lp']),1)

    def test_operation_lock_prevents_overlapping_mutation(self):
        with ops.lock(self.root):
            with self.assertRaisesRegex(ValueError,'operation is active'):
                with ops.lock(self.root):
                    pass

    def test_capped_public_feed_remains_partial(self):
        config={'id':'public','url':'https://example.org/feed','format':'jsonfeed','max_items':1}
        data=json.dumps({'title':'Fictional','items':[{'id':str(k),'title':str(k),'summary':'Example'} for k in range(2)]}).encode()
        result=sources.public_envelope(config,self.profile,'2026-10-24',fetcher=lambda url:data)
        self.assertEqual(result['status'],'partial')
        self.assertFalse(result['complete'])

    def test_source_import_rejects_cache_claim_and_wrong_date(self):
        path=self.root/'work/snapshot.json'
        n.save(path,self.snapshot)
        envelope={**self.snapshot['sources']['calendar'],'source':'calendar','date':'2026-10-24','timezone':'Etc/UTC','method':'local_cache'}
        with self.assertRaisesRegex(ValueError,'complete live evidence'):
            sources.import_source(self.root,path,envelope)
        envelope['date']='2026-10-23'
        with self.assertRaisesRegex(ValueError,'date/time zone'):
            sources.import_source(self.root,path,envelope)

    def test_pilot_distinguishes_partial_delivery_from_acceptance(self):
        for day in ('22','23','24'):
            result=ops.pilot(self.root,{'date':'2026-10-'+day,'started_at':'2026-10-'+day+'T05:00:00+00:00','finished_at':'2026-10-'+day+'T05:50:00+00:00',
                'delivery_status':'emailed','delivered_at':'2026-10-'+day+'T05:48:00+00:00','coverage_complete':False,'print_status':'skipped'})
        self.assertTrue(result['pilot_complete'])
        self.assertFalse(result['full_coverage_accepted'])
        self.assertEqual(result['start_adjustment_minutes'],5)


if __name__=='__main__':
    unittest.main()
