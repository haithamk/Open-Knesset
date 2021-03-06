from datetime import datetime
from django.test import TestCase
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.urlresolvers import reverse
from django.utils.encoding import smart_str, smart_unicode
from django.contrib.auth.models import User, Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.utils import simplejson as json

from actstream.models import Action
from tagging.models import Tag, TaggedItem

from knesset.laws.models import Vote,Bill,KnessetProposal
from knesset.mks.models import Member


just_id = lambda x: x.id

class BillViewsTest(TestCase):

    def setUp(self):
        self.vote_1 = Vote.objects.create(time=datetime.now(),
                                          title='vote 1')
        self.vote_2 = Vote.objects.create(time=datetime.now(), 
                                          title='vote 2')
        self.jacob = User.objects.create_user('jacob', 'jacob@example.com',
                                              'JKM')
        self.bill_1 = Bill.objects.create(stage='1', title='bill 1', popular_name="The Bill")
        self.bill_2 = Bill.objects.create(stage='2', title='bill 2')
        self.bill_3 = Bill.objects.create(stage='2', title='bill 1')
        self.kp_1 = KnessetProposal.objects.create(booklet_number=2, bill=self.bill_1)
        self.mk_1 = Member.objects.create(name='mk 1')

    def testBillList(self):
        res = self.client.get(reverse('bill-list'))
        self.assertEqual(res.status_code, 200)
        self.assertTemplateUsed(res, 'laws/bill_list.html')
        object_list = res.context['object_list']
        self.assertEqual(map(just_id, object_list), 
                         [ self.bill_1.id, self.bill_2.id, self.bill_3.id ])
    def testBillListByStage(self):
        res = self.client.get(reverse('bill-list'), {'stage': 'all'})
        object_list = res.context['object_list']
        self.assertEqual(map(just_id, object_list), 
                         [ self.bill_1.id, self.bill_2.id, self.bill_3.id])
        res = self.client.get(reverse('bill-list'), {'stage': '1'})
        object_list = res.context['object_list']
        self.assertEqual(map(just_id, object_list), [self.bill_1.id])
        res = self.client.get(reverse('bill-list'), {'stage': '2'})
        object_list = res.context['object_list']
        self.assertEqual(map(just_id, object_list), [self.bill_2.id, self.bill_3.id])

    def testBillListByBooklet(self):
        res = self.client.get(reverse('bill-list'), {'booklet': '2'})
        object_list = res.context['object_list']
        self.assertEqual(map(just_id, object_list), [self.bill_1.id])

    def testBillDetail(self):
        res = self.client.get(reverse('bill-detail',
                                 kwargs={'pk': self.bill_1.id}))
        self.assertEqual(res.status_code, 200)
        self.assertTemplateUsed(res,
                                'laws/bill_detail.html')
        self.assertEqual(res.context['object'].id, self.bill_1.id)
        
    def test_bill_detail_by_slug(self):
        res = self.client.get(reverse('bill-detail-with-slug',
                                 kwargs={'slug': self.bill_1.slug,
                                         'pk': self.bill_1.id}))
        self.assertEqual(res.status_code, 200)
        self.assertTemplateUsed(res,
                                'laws/bill_detail.html')
        self.assertEqual(res.context['object'].id, self.bill_1.id)
        
    def test_bill_popular_name(self):
        res = self.client.get('/bill/'+self.bill_1.popular_name+'/')
        self.assertEqual(res.status_code, 404)
        
    def test_bill_popular_name_by_slug(self):
        res = self.client.get(reverse('bill-detail-with-slug',
                                 kwargs={'slug': self.bill_1.popular_name_slug,
                                         'pk': self.bill_1.id}))
        self.assertEqual(res.status_code, 200)
        self.assertTemplateUsed(res,
                                'laws/bill_detail.html')
        self.assertEqual(res.context['object'].id, self.bill_1.id)
    '''
    def test_bill_detail_hebrew_name_by_slug(self):
        res = self.client.get(reverse('bill-detail',
                                 kwargs={'slug': self.bill_hebrew_name.slug}))
        self.assertEqual(res.status_code, 200)
        self.assertTemplateUsed(res,
                                'laws/bill_detail.html')
        self.assertEqual(res.context['object'].id, self.bill_1.id)
    '''
    def testLoginRequired(self):
        res = self.client.post(reverse('bill-detail',
                           kwargs={'pk': self.bill_1.id}))
        self.assertEqual(res.status_code, 302)
        self.assertTrue(res['location'].startswith('%s%s'  %
                                       ('http://testserver', settings.LOGIN_URL)))

    def testPOSTApprovalVote(self):
        self.assertTrue(self.client.login(username='jacob', password='JKM'))
        res = self.client.post(reverse('bill-detail',
                           kwargs={'pk': self.bill_1.id}),
                               {'user_input_type': 'approval vote',
                                'vote_id': self.vote_1.id})
        self.assertEqual(res.status_code, 302)
        self.bill_1 = Bill.objects.get(pk=self.bill_1.id)
        self.assertEqual(self.bill_1.approval_vote, self.vote_1)
        self.assertEqual(self.bill_1.first_vote, None)
        self.assertFalse(self.bill_1.pre_votes.all())
        # cleanup
        self.bill_1.approval_vote = None
        self.bill_1.save()
        self.client.logout()

    def testPOSTFirstVote(self):
        self.assertTrue(self.client.login(username='jacob', password='JKM'))
        res = self.client.post(reverse('bill-detail',
                           kwargs={'pk': self.bill_1.id}),
                               {'user_input_type': 'first vote',
                                'vote_id': self.vote_2.id})
        self.assertEqual(res.status_code, 302)
        self.bill_1 = Bill.objects.get(pk=self.bill_1.id)
        self.assertEqual(self.bill_1.first_vote, self.vote_2)
        self.assertEqual(self.bill_1.approval_vote, None)
        self.assertFalse(self.bill_1.pre_votes.all())
        # cleanup
        self.bill_1.first_vote = None
        self.bill_1.save()
        self.client.logout()

    def testPOSTPreVote(self):
        self.assertTrue(self.client.login(username='jacob', password='JKM'))
        res = self.client.post(reverse('bill-detail',
                           kwargs={'pk': self.bill_1.id}),
                               {'user_input_type': 'pre vote',
                                'vote_id': self.vote_2.id})
        self.assertEqual(res.status_code, 302)
        self.bill_1 = Bill.objects.get(pk=self.bill_1.id)
        self.assertTrue(self.vote_2 in self.bill_1.pre_votes.all())
        self.assertEqual(self.bill_1.first_vote, None)
        self.assertEqual(self.bill_1.approval_vote, None)
        # cleanup
        self.bill_1.pre_votes.clear()
        self.client.logout()
        self.client.logout()

    ''' TODO: test the feed
    def testFeeds(self):
        res = self.client.get(reverse('bills-feed'))
        self.assertEqual(res.status_code, 200)
        ...use feedparser to analyze res
    '''

    def tearDown(self):
        self.vote_1.delete()
        self.vote_2.delete()
        self.bill_1.delete()
        self.bill_2.delete()
        self.bill_3.delete()
        self.jacob.delete()
        self.mk_1.delete()




class VoteViewsTest(TestCase):

    def setUp(self):
        self.jacob = User.objects.create_user('jacob', 'jacob@example.com',
                                              'JKM')
        self.adrian = User.objects.create_user('adrian', 'adrian@example.com',
                                              'ADRIAN')
        g, created = Group.objects.get_or_create(name='Valid Email')
        ct = ContentType.objects.get_for_model(Tag)
        p = Permission.objects.get(codename='add_tag', content_type=ct)        
        g.permissions.add(p)
        
        self.adrian.groups.add(g)
        self.vote_1 = Vote.objects.create(time=datetime(2001, 9, 11),
                                          title='vote 1')
        self.vote_2 = Vote.objects.create(time=datetime.now(), 
                                          title='vote 2')
        self.tag_1 = Tag.objects.create(name='tag1')
        self.ti = TaggedItem._default_manager.create(tag=self.tag_1,
                                                     content_type=ContentType.objects.get_for_model(Vote), 
                                                     object_id=self.vote_1.id)

    def testVoteList(self):
        res = self.client.get(reverse('vote-list'))
        self.assertEqual(res.status_code, 200)
        self.assertTemplateUsed(res, 'laws/vote_list.html')
        object_list = res.context['object_list']
        self.assertEqual(map(just_id, object_list), 
                         [ self.vote_2.id, self.vote_1.id, ])

    def testVoteDetail(self):
        res = self.client.get(reverse('vote-detail',
                                 kwargs={'pk': self.vote_1.id}))
        self.assertEqual(res.status_code, 200)
        self.assertTemplateUsed(res,
                                'laws/vote_detail.html')
        self.assertEqual(res.context['vote'].id, self.vote_1.id)

    def test_vote_tag_cloud(self):
        res = self.client.get(reverse('vote-tags-cloud'))
        self.assertEqual(res.status_code, 200)
        self.assertTemplateUsed(res, 'laws/vote_tags_cloud.html')

    def test_add_tag_to_vote_login_required(self):
        url = reverse('add-tag-to-object',
                                 kwargs={'object_type':'vote','object_id': self.vote_2.id})
        res = self.client.post(url, {'tag_id':self.tag_1})
        self.assertRedirects(res, "%s?next=%s" % (settings.LOGIN_URL, url), status_code=302)

    def test_add_tag_to_vote(self):
        self.assertTrue(self.client.login(username='jacob', password='JKM'))
        url = reverse('add-tag-to-object',
                                 kwargs={'object_type':'vote','object_id': self.vote_2.id})
        res = self.client.post(url, {'tag_id':self.tag_1.id})
        self.assertEqual(res.status_code, 200)

    def test_create_tag_permission_required(self):
        self.assertTrue(self.client.login(username='jacob', password='JKM'))
        url = reverse('create-tag',
                                 kwargs={'object_type':'vote','object_id': self.vote_2.id})
        res = self.client.post(url, {'tag':'new tag'})
        self.assertRedirects(res, "%s?next=%s" % (settings.LOGIN_URL, url), status_code=302)

    def test_create_tag(self):
        self.assertTrue(self.client.login(username='adrian', password='ADRIAN'))
        url = reverse('create-tag',
                                 kwargs={'object_type':'vote','object_id': self.vote_2.id})
        res = self.client.post(url, {'tag':'new tag'})
        self.assertEqual(res.status_code, 200)

    def tearDown(self):
        self.vote_1.delete()
        self.vote_2.delete()

class testVoteAPI(TestCase):
    def setUp(self):
        self.vote_1 = Vote.objects.create(time=datetime(2001, 9, 11),
                                          title='vote 1')
        self.vote_2 = Vote.objects.create(time=datetime.now(), 
                                          title='vote 2')

    def testDaysBackAPI(self):
        res = self.client.get(reverse('vote-handler'), {'days_back': '300'}) 
        self.assertEqual(res.status_code,200)
        votes = json.loads(res.content)
        self.assertEqual(map(lambda x: x['title'], votes), [self.vote_2.title])
        res = self.client.get(reverse('vote-handler'), {'days_back': '30000'}) 
        self.assertEqual(res.status_code,200)
        votes = json.loads(res.content)
        self.assertEqual(set(map(lambda x: x['title'], votes)), set([self.vote_1.title, self.vote_2.title]))

    def tearDown(self):
        self.vote_1.delete()
        self.vote_2.delete()

class BillStreamTest(TestCase):
    def setUp(self):
        self.vote_1 = Vote.objects.create(time=datetime(2010, 12, 18),
                                          title='vote 1')
        self.vote_2 = Vote.objects.create(time=datetime(2011, 4, 4),
                                          title='vote 2')
        self.bill = Bill.objects.create(stage='1', title='bill 1', popular_name="The Bill")
        self.bill.pre_votes.add(self.vote_1)
        self.bill.first_vote = self.vote_2
        self.kp_1 = KnessetProposal.objects.create(booklet_number=2, bill=self.bill, date=datetime(2005, 1, 22))

    def testGenerate(self):
        self.bill.generate_activity_stream()
        s = Action.objects.stream_for_actor(self.bill)
        self.assertEqual(s.count(),3)

    def tearDown(self):
        self.bill.pre_votes.all().delete()
        self.vote_1.delete()
        self.vote_2.delete()
        self.kp_1.delete()
        self.bill.delete()


# TODO: add testing for suggest_tag, vote_on_tag and tagged-votes views
