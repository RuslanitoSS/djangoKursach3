from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from django.conf import settings
import os

# Импорты моделей
from cinema.models import User, Franchise, Chapter, Genre
from fan_clubs.models import FanClub, FanClubPhoto, FanClubMembership, FanClubApplicationAttachment


class Command(BaseCommand):
    help = 'Загружает тестовые данные для приложения Fan Clubs'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Очистить существующие данные перед загрузкой'
        )
        parser.add_argument(
            '--clubs',
            type=int,
            default=5,
            help='Количество клубов для создания (по умолчанию: 5)'
        )
        parser.add_argument(
            '--members',
            type=int,
            default=10,
            help='Количество пользователей для создания (по умолчанию: 10)'
        )

    def handle(self, *args, **options):
        clear = options['clear']
        clubs_count = options['clubs']
        members_count = options['members']

        if clear:
            self.stdout.write(self.style.WARNING('🗑️  Очистка существующих данных...'))
            FanClubApplicationAttachment.objects.all().delete()
            FanClubPhoto.objects.all().delete()
            FanClubMembership.objects.all().delete()
            FanClub.objects.all().delete()
            User.objects.filter(username__startswith='test_').delete()
            self.stdout.write(self.style.SUCCESS('✅ Данные очищены'))

        self.stdout.write(self.style.SUCCESS('🚀 Начинаем загрузку тестовых данных...'))

        # ======================================================================
        # 1. СОЗДАНИЕ ТЕСТОВЫХ ПОЛЬЗОВАТЕЛЕЙ
        # ======================================================================
        self.stdout.write('\n📝 Создание пользователей...')
        
        users = []
        passwords = {}
        
        # Создаём тестовых пользователей
        for i in range(1, members_count + 1):
            username = f'test_user_{i}'
            email = f'test{i}@example.com'
            password = f'TestPass{i}!'
            
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    'email': email,
                    'first_name': f'Test{i}',
                    'last_name': f'User{i}',
                    'is_active': True,
                }
            )
            if created:
                user.set_password(password)
                user.save()
                passwords[username] = password
            
            users.append(user)
            self.stdout.write(f'  {"✅" if created else "⚠️"} {username} ({email})')

        # Создаём администратора клубов
        admin_user, created = User.objects.get_or_create(
            username='club_admin',
            defaults={
                'email': 'admin@fanclubs.com',
                'first_name': 'Club',
                'last_name': 'Administrator',
                'is_staff': True,
                'is_superuser': True,
                'is_active': True,
            }
        )
        if created:
            admin_user.set_password('AdminPass123!')
            admin_user.save()
            passwords['club_admin'] = 'AdminPass123!'
        
        users.append(admin_user)
        self.stdout.write(f'  {"✅" if created else "⚠️"} club_admin (admin@fanclubs.com)')

        # ======================================================================
        # 2. ПОЛУЧЕНИЕ КОНТЕНТА ИЗ CINEMA (Franchise, Chapter)
        # ======================================================================
        self.stdout.write('\n🎬 Получение контента из cinema...')
        
        franchises = list(Franchise.objects.all()[:5])
        chapters = list(Chapter.objects.all()[:10])
        
        if not franchises:
            self.stdout.write(self.style.WARNING('  ⚠️  Франшизы не найдены, создаём тестовые...'))
            for i in range(1, 4):
                franchise, _ = Franchise.objects.get_or_create(
                    title=f'Test Franchise {i}',
                    defaults={'created_at': timezone.now()}
                )
                franchises.append(franchise)
        
        if not chapters:
            self.stdout.write(self.style.WARNING('  ⚠️  Главы не найдены, создаём тестовые...'))
            for i in range(1, 6):
                chapter, _ = Chapter.objects.get_or_create(
                    title=f'Test Chapter {i}',
                    defaults={
                        'release_date': timezone.now().date() - timedelta(days=i*10),
                        'content_type': 'movie',
                        'age_rating': 16,
                    }
                )
                chapters.append(chapter)
        
        self.stdout.write(f'  ✅ Найдено франшиз: {len(franchises)}')
        self.stdout.write(f'  ✅ Найдено глав: {len(chapters)}')

        # ======================================================================
        # 3. СОЗДАНИЕ ФАН-КЛУБОВ
        # ======================================================================
        self.stdout.write(f'\n🏆 Создание {clubs_count} фан-клубов...')
        
        club_names = [
            'Поклонники Звёздных Войн',
            'Клуб Любителей Марвел',
            'Фанаты Гарри Поттера',
            'Общество Владельцев Колец',
            'Защитники Галактики',
            'Лига Справедливости Фанов',
            'Клуб Киноманов',
            'Фан-клуб Режиссёров',
            'Сообщество Сериаломанов',
            'Кинолюбители 24/7',
        ]
        
        club_descriptions = [
            'Добро пожаловать в клуб настоящих поклонников! Обсуждаем теории, делимся фанартом и организуем просмотры.',
            'Присоединяйтесь к нашему сообществу! Эксклюзивный контент, ранний доступ к материалам и живое общение.',
            'Клуб для тех, кто живёт кинематографом! Встречи, обсуждения, конкурсы и много интересного.',
            'Объединяем фанатов со всего мира! Делитесь мнениями, находите друзей и участвуйте в мероприятиях.',
            'Элитное сообщество ценителей качественного контента. Только проверенные участники и эксклюзивные материалы.',
        ]
        
        clubs = []
        for i in range(clubs_count):
            name = club_names[i % len(club_names)]
            if clubs_count > len(club_names):
                name = f'{name} #{i // len(club_names) + 1}'
            
            club, created = FanClub.objects.get_or_create(
                slug=f'fan-club-{i+1}',
                defaults={
                    'title': name,
                    'description': club_descriptions[i % len(club_descriptions)],
                    'franchise': franchises[i % len(franchises)] if franchises else None,
                    'chapter': chapters[i % len(chapters)] if chapters else None,
                    'created_by': admin_user,
                    'requirements_text': 'Для вступления необходимо:\n1. Быть старше 16 лет\n2. Любить кинематограф\n3. Прикрепить фото с любимым персонажем',
                    'application_questions': [
                        {'id': 'q1', 'text': 'Почему вы хотите вступить в наш клуб?'},
                        {'id': 'q2', 'text': 'Ваш любимый фильм/сериал?'},
                        {'id': 'q3', 'text': 'Как давно вы следите за франшизой?'},
                    ],
                    'max_application_photos': 3,
                    'max_club_photos': 20,
                    'is_active': True,
                }
            )
            clubs.append(club)
            self.stdout.write(f'  {"✅" if created else "⚠️"} {club.title}')

        # ======================================================================
        # 4. СОЗДАНИЕ ЧЛЕНСТВ В КЛУБАХ
        # ======================================================================
        self.stdout.write('\n👥 Создание членств в клубах...')
        
        statuses = ['approved', 'approved', 'approved', 'pending', 'rejected']
        roles = ['admin', 'member', 'member', 'member', 'member']
        
        membership_count = 0
        for club in clubs:
            # Создаём администратора клуба (создатель)
            admin_membership, _ = FanClubMembership.objects.get_or_create(
                user=admin_user,
                club=club,
                defaults={
                    'role': 'admin',
                    'status': 'approved',
                    'joined_at': timezone.now() - timedelta(days=30),
                    'application_data': {},
                }
            )
            membership_count += 1
            
            # Добавляем случайных участников
            club_members = users[:5]  # Первые 5 пользователей
            for j, user in enumerate(club_members):
                if user == admin_user:
                    continue
                
                status = statuses[j % len(statuses)]
                role = 'member'
                
                membership, created = FanClubMembership.objects.get_or_create(
                    user=user,
                    club=club,
                    defaults={
                        'role': role,
                        'status': status,
                        'joined_at': timezone.now() - timedelta(days=20-j) if status == 'approved' else None,
                        'application_data': {
                            'q1': f'Хочу быть частью сообщества {club.title}',
                            'q2': 'Любимый фильм - Классика кинематографа',
                            'q3': f'{j+1} лет',
                        },
                        'review_comment': 'Одобрено' if status == 'approved' else 'Не подошёл по критериям' if status == 'rejected' else '',
                        'reviewed_by': admin_user if status != 'pending' else None,
                    }
                )
                if created:
                    membership_count += 1
                    self.stdout.write(f'  ✅ {user.username} → {club.title} ({status})')

        self.stdout.write(self.style.SUCCESS(f'\n📊 Всего создано членств: {membership_count}'))

        # ======================================================================
        # 5. СОЗДАНИЕ ФОТО КЛУБОВ
        # ======================================================================
        self.stdout.write('\n📸 Создание фото в галереях клубов...')
        
        photo_count = 0
        for club in clubs:
            # Создаём от 3 до 10 фото для каждого клуба
            num_photos = 3 + (hash(club.title) % 8)
            
            for j in range(num_photos):
                if not club.can_add_club_photo():
                    break
                
                # Создаём заглушку фото (в реальности нужно загрузить файлы)
                # Для тестов создаём запись без файла
                photo, created = FanClubPhoto.objects.get_or_create(
                    club=club,
                    caption=f'Фото {j+1} для {club.title}',
                    defaults={
                        'uploaded_by': admin_user,
                        'uploaded_at': timezone.now() - timedelta(days=15-j),
                    }
                )
                if created:
                    photo_count += 1
            
            self.stdout.write(f'  ✅ {club.title}: {club.get_photos_count()} фото')

        self.stdout.write(self.style.SUCCESS(f'\n📊 Всего создано фото: {photo_count}'))

        # ======================================================================
        # 6. СОЗДАНИЕ ЗАЯВОК С ВЛОЖЕНИЯМИ
        # ======================================================================
        self.stdout.write('\n📎 Создание заявок с вложениями...')
        
        attachment_count = 0
        pending_memberships = FanClubMembership.objects.filter(status='pending')[:5]
        
        for membership in pending_memberships:
            # Добавляем от 1 до 3 вложений к каждой заявке
            num_attachments = 1 + (hash(membership.user.username) % 3)
            
            for j in range(num_attachments):
                if not membership.can_add_more_application_photos():
                    break
                
                attachment, created = FanClubApplicationAttachment.objects.get_or_create(
                    membership=membership,
                    caption=f'Фото {j+1} для проверки',
                    defaults={
                        'uploaded_at': timezone.now() - timedelta(days=5-j),
                    }
                )
                if created:
                    attachment_count += 1
            
            self.stdout.write(f'  ✅ {membership.user.username} → {membership.club.title}: {membership.get_application_photos_count()} фото')

        self.stdout.write(self.style.SUCCESS(f'\n📊 Всего создано вложений: {attachment_count}'))

        # ======================================================================
        # ИТОГИ
        # ======================================================================
        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.SUCCESS('✅ ЗАГРУЗКА ТЕСТОВЫХ ДАННЫХ ЗАВЕРШЕНА!'))
        self.stdout.write('='*60)
        self.stdout.write(self.style.SUCCESS(f'👤 Пользователей: {User.objects.filter(username__startswith="test_").count() + 1}'))
        self.stdout.write(self.style.SUCCESS(f'🏆 Фан-клубов: {FanClub.objects.count()}'))
        self.stdout.write(self.style.SUCCESS(f'👥 Членств: {FanClubMembership.objects.count()}'))
        self.stdout.write(self.style.SUCCESS(f'📸 Фото в галереях: {FanClubPhoto.objects.count()}'))
        self.stdout.write(self.style.SUCCESS(f'📎 Вложений в заявках: {FanClubApplicationAttachment.objects.count()}'))
        self.stdout.write('='*60)
        
        self.stdout.write(self.style.WARNING('\n🔐 ДАННЫЕ ДЛЯ ВХОДА:'))
        self.stdout.write(f'  👑 Администратор: club_admin / AdminPass123!')
        for i in range(1, min(6, members_count + 1)):
            username = f'test_user_{i}'
            if username in passwords:
                self.stdout.write(f'  👤 {username} / {passwords[username]}')
        
        self.stdout.write(self.style.SUCCESS('\n🎉 Удачи в тестировании!'))