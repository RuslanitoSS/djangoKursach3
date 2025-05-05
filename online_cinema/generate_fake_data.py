import os
import django
import random
import datetime
from faker import Faker
from django.utils import timezone

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'online_cinema.settings')  # замените на имя вашего проекта
django.setup()

from cinema.models import (
    User, UserPaymentMethod, Subscription, UserSubscription, Genre, Franchise,
    Chapter, Episode, Person, ChapterPersonRole, Comment, Review, Rating,
    Playlist, PlaylistChapter, ViewHistory
)

fake = Faker()

def create_users(n=10):
    users = []
    for _ in range(n):
        user = User.objects.create_user(
            username=fake.user_name(),
            email=fake.email(),
            password="password123",
            description=fake.text(),
        )
        users.append(user)
    return users

def create_subscriptions():
    titles = ["Basic", "Premium", "VIP"]
    for title in titles:
        Subscription.objects.create(
            title=title,
            price_usd=round(random.uniform(5, 30), 2),
            duration_days=random.choice([30, 90, 180]),
            description=fake.text()
        )

def create_payment_methods(users):
    for user in users:
        for _ in range(random.randint(1, 2)):
            UserPaymentMethod.objects.create(
                user=user,
                payment_type=random.choice([choice[0] for choice in UserPaymentMethod.PAYMENT_TYPE_CHOICES]),
                provider_id=fake.uuid4(),
                masked_card_number=f"**** **** **** {random.randint(1000, 9999)}",
                card_brand=random.choice(["Visa", "MasterCard", "Amex"]),
                card_expiry_month=random.randint(1, 12),
                card_expiry_year=timezone.now().year + random.randint(1, 5),
            )

def create_user_subscriptions(users):
    subscriptions = list(Subscription.objects.all())
    for user in users:
        sub = random.choice(subscriptions)
        start = timezone.now() - datetime.timedelta(days=random.randint(0, 60))
        usub = UserSubscription.objects.create(
            user=user,
            subscription=sub,
            start_date=start,
            is_active=True,
        )
        usub.payment_methods.set(user.payment_methods.all())

def create_genres():
    for name in ["Action", "Comedy", "Drama", "Fantasy", "Sci-Fi"]:
        Genre.objects.get_or_create(name=name)

def create_people(n=10):
    for _ in range(n):
        Person.objects.create(
            first_name=fake.first_name(),
            last_name=fake.last_name(),
            birth_date=fake.date_of_birth(minimum_age=20, maximum_age=70),
            country=fake.country(),
            photo_url=fake.image_url(),
            biography=fake.text()
        )

def create_franchises(n=3):
    franchises = []
    for _ in range(n):
        f = Franchise.objects.create(title=fake.catch_phrase())
        franchises.append(f)
    return franchises

def create_chapters(franchises):
    genres = list(Genre.objects.all())
    for f in franchises:
        for i in range(1, 4):
            chapter = Chapter.objects.create(
                franchise=f,
                franchise_relation=random.choice(['main', 'spinoff', 'side']),
                title=f"{f.title} Chapter {i}",
                description=fake.text(),
                release_date=fake.date_between(start_date='-3y', end_date='today'),
                required_subscription=random.choice(Subscription.objects.all()),
                chapter_number=i,
                country=fake.country(),
                age_rating=random.randint(6, 18),
                content_type=random.choice(['movie', 'series']),
                view_count=random.randint(0, 1000),
                trailer_url=fake.url()
            )
            chapter.genres.set(random.sample(genres, k=random.randint(1, 3)))

def create_episodes():
    chapters = Chapter.objects.all()
    for chapter in chapters:
        for i in range(1, random.randint(2, 5)):
            Episode.objects.create(
                chapter=chapter,
                episode_number=i,
                title=f"Episode {i}",
                duration=datetime.timedelta(minutes=random.randint(20, 90)),
                release_date=chapter.release_date,
                thumbnail_url=fake.image_url()
            )

def assign_roles():
    people = list(Person.objects.all())
    chapters = Chapter.objects.all()
    for chapter in chapters:
        for role in ['actor', 'director', 'producer']:
            ChapterPersonRole.objects.create(
                chapter=chapter,
                person=random.choice(people),
                role=role
            )

def create_comments_reviews_ratings(users):
    chapters = Chapter.objects.all()
    for user in users:
        for chapter in random.sample(list(chapters), k=3):
            Comment.objects.create(user=user, chapter=chapter, text=fake.sentence())
            Review.objects.create(user=user, chapter=chapter, text=fake.paragraph())
            Rating.objects.create(user=user, chapter=chapter, score=random.randint(1, 10))

def create_playlists(users):
    chapters = list(Chapter.objects.all())
    for user in users:
        pl = Playlist.objects.create(
            user=user,
            title=fake.catch_phrase(),
            description=fake.text(),
            is_public=random.choice([True, False]),
            cover_image_url=fake.image_url(),
        )
        for chapter in random.sample(chapters, k=3):
            PlaylistChapter.objects.create(playlist=pl, chapter=chapter)

def create_view_history(users):
    chapters = list(Chapter.objects.all())
    for user in users:
        for chapter in random.sample(chapters, k=5):
            ViewHistory.objects.create(user=user, chapter=chapter)

def run_all():
    users = create_users(10)
    create_subscriptions()
    create_payment_methods(users)
    create_user_subscriptions(users)
    create_genres()
    create_people(10)
    franchises = create_franchises()
    create_chapters(franchises)
    create_episodes()
    assign_roles()
    create_comments_reviews_ratings(users)
    create_playlists(users)
    create_view_history(users)
    print("Fake data generated.")

if __name__ == "__main__":
    run_all()
