import datetime
from django.db import transaction
from django.core.management.base import BaseCommand
from django.utils.translation import gettext_lazy as _

from cinema.models import Genre, Franchise, Chapter, Person, Episode, ChapterPersonRole


class Command(BaseCommand):
    help = 'Наполняет базу данных базовыми франшизами: Властелин колец, Гарри Поттер, Тёмный рыцарь'

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('🎬 Начинаем наполнение базы данных...'))

        with transaction.atomic():
            # ================= 1. ЖАНРЫ =================
            self.stdout.write('🎭 Создаём жанры...')
            genres = self._setup_genres()
            self.stdout.write(self.style.SUCCESS(f'   ✓ Создано жанров: {len(genres)}'))

            # ================= 2. ФРАНШИЗЫ =================
            self.stdout.write('📚 Создаём франшизы...')
            franchises = self._setup_franchises()
            self.stdout.write(self.style.SUCCESS(f'   ✓ Создано франшиз: {len(franchises)}'))

            # ================= 3. ПЕРСОНЫ =================
            self.stdout.write('👤 Создаём персон...')
            persons = self._setup_persons()
            self.stdout.write(self.style.SUCCESS(f'   ✓ Создано персон: {len(persons)}'))

            # ================= 4. ГЛАВЫ + ЖАНРЫ =================
            self.stdout.write('🎞️ Создаём главы (фильмы/сериалы)...')
            chapters = self._setup_chapters(franchises, genres)
            self.stdout.write(self.style.SUCCESS(f'   ✓ Создано глав: {len(chapters)}'))

            # ================= 5. ЭПИЗОДЫ =================
            self.stdout.write('📼 Создаём эпизоды...')
            episodes_count = self._setup_episodes(chapters)
            self.stdout.write(self.style.SUCCESS(f'   ✓ Создано эпизодов: {episodes_count}'))

            # ================= 6. РОЛИ (ChapterPersonRole) =================
            self.stdout.write('🔗 Создаём связи персон с главами...')
            created_roles = self._setup_roles(chapters, persons)
            self.stdout.write(self.style.SUCCESS(f'   ✓ Создано ролевых связей: {created_roles}'))

            # ================= ИТОГ =================
            self.stdout.write('\n' + '='*60)
            self.stdout.write(self.style.SUCCESS('✅ ГОТОВО! Статистика в базе данных:'))
            self.stdout.write('='*60)
            self.stdout.write(f"🎭 Жанров:          {Genre.objects.count()}")
            self.stdout.write(f"📚 Франшиз:         {Franchise.objects.count()}")
            self.stdout.write(f"👤 Персон:          {Person.objects.count()}")
            self.stdout.write(f"🎞️ Глав:            {Chapter.objects.count()}")
            self.stdout.write(f"📼 Эпизодов:        {Episode.objects.count()}")
            self.stdout.write(f"🔗 Ролевых связей:  {ChapterPersonRole.objects.count()}")
            self.stdout.write('='*60)

    # ================= ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ =================

    def _setup_genres(self):
        """Создаёт или получает жанры"""
        genre_names = [
            "Фэнтези", "Приключения", "Боевик", "Криминал",
            "Драма", "Триллер", "Семейный", "Мистика", "Документальный"
        ]
        genres = {}
        for name in genre_names:
            g, _ = Genre.objects.get_or_create(name=name)
            genres[name] = g
        return genres

    def _setup_franchises(self):
        """Создаёт или получает франшизы"""
        franchise_data = {
            "lotr": "Властелин колец",
            "hp": "Гарри Поттер",
            "tdk": "Тёмный рыцарь (Трилогия)",
        }
        franchises = {}
        for key, title in franchise_data.items():
            f, _ = Franchise.objects.get_or_create(title=title)
            franchises[key] = f
        return franchises

    def _setup_persons(self):
        """Создаёт или получает персон"""
        persons_data = [
            ("Питер", "Джексон", "1961-10-31", "Новая Зеландия", "Режиссёр и продюсер, создавший кинематографическую адаптацию трилогии Толкина."),
            ("Крис", "Коламбус", "1958-09-10", "США", "Американский режиссёр, снявший первые два фильма о Гарри Поттере."),
            ("Дэвид", "Йейтс", "1963-10-08", "Великобритания", "Британский режиссёр, завершивший киносагу о Гарри Поттере."),
            ("Кристофер", "Нолан", "1970-07-30", "Великобритания", "Британо-американский режиссёр, известный нелинейным повествованием."),
            ("Фрэн", "Уолш", "1959-01-23", "Новая Зеландия", "Продюсер и сценарист, супруга Питера Джексона."),
            ("Филиппа", "Бойенс", "1962-09-01", "Новая Зеландия", "Сценаристка и продюсер, соавтор экранизации «Властелина колец»."),
            ("Стив", "Кловс", "1960-08-18", "США", "Американский сценарист, адаптировавший 7 из 8 книг о Гарри Поттере."),
            ("Джонатан", "Нолан", "1976-06-06", "Великобритания", "Британский писатель и сценарист, брат Кристофера Нолана."),
            ("Дэвид", "Хейман", "1961-07-26", "Великобритания", "Продюсер, инициировавший создание франшизы «Гарри Поттер»."),
            ("Эмма", "Томас", "1971-12-09", "Великобритания", "Продюсер, супруга Кристофера Нолана."),
            ("Ли", "Смит", "1960-03-01", "Австралия", "Австралийский монтажер, лауреат «Оскара»."),
            ("Элайджа", "Вуд", "1981-01-28", "США", "Исполнитель роли Фродо Бэггинса."),
            ("Иэн", "Маккеллен", "1939-05-25", "Великобритания", "Легендарный британский актёр, сыгравший Гэндальфа."),
            ("Вигго", "Мортенсен", "1958-10-20", "США", "Актёр датско-американского происхождения, исполнитель роли Арагорна."),
            ("Дэниел", "Рэдклифф", "1989-07-23", "Великобритания", "Британский актёр, прославившийся ролью Гарри Поттера."),
            ("Эмма", "Уотсон", "1990-04-15", "Великобритания", "Британская актриса, исполнительница роли Гермионы Грейнджер."),
            ("Руперт", "Гринт", "1988-08-24", "Великобритания", "Британский актёр, исполнитель роли Рона Уизли."),
            ("Кристиан", "Бейл", "1974-01-30", "Великобритания", "Британский актёр, известный радикальными трансформациями для ролей."),
            ("Хит", "Леджер", "1979-04-04", "Австралия", "Австралийский актёр, посмертно получивший «Оскар» за роль Джокера."),
            ("Гэри", "Олдман", "1958-03-21", "Великобритания", "Британский актёр, исполнитель роли комиссара Гордона."),
        ]
        
        persons = {}
        for first, last, birth, country, bio in persons_data:
            p, _ = Person.objects.get_or_create(
                first_name=first, last_name=last,
                defaults={
                    "birth_date": datetime.date.fromisoformat(birth),
                    "country": country,
                    "biography": bio,
                    "photo_url": f"https://example.com/persons/{first.lower()}_{last.lower()}.jpg"
                }
            )
            persons[f"{first}_{last}"] = p
        return persons

    def _create_chapter(self, fk_franchise, num, title, date, country, rating, ctype, rel, desc, poster, trailer, genre_keys, genres):
        """Вспомогательный метод для создания главы"""
        ch, _ = Chapter.objects.get_or_create(
            franchise=fk_franchise, chapter_number=num,
            defaults={
                "title": title, "release_date": datetime.date.fromisoformat(date),
                "country": country, "age_rating": rating, "content_type": ctype,
                "franchise_relation": rel, "description": desc,
                "poster_image": f"posters/{poster}", "trailer_url": trailer,
                "rating_cache": 0.0, "view_count": 0, "required_subscription": None
            }
        )
        ch.genres.set([genres[k] for k in genre_keys])
        return ch

    def _setup_chapters(self, franchises, genres):
        """Создаёт главы для всех франшиз"""
        chapters = {}

        # Властелин колец
        chapters["lotr_1"] = self._create_chapter(
            franchises["lotr"], 1, "Братство кольца", "2001-12-19", "Новая Зеландия / США", 12, "movie", "main",
            "Хоббит Фродо наследует Единое Кольцо и отправляется в опасное путешествие.", "lotr_fellowship.jpg",
            "https://www.youtube.com/watch?v=V75dMMIW2B4", ["Фэнтези", "Приключения", "Боевик"], genres)
        
        chapters["lotr_2"] = self._create_chapter(
            franchises["lotr"], 2, "Две крепости", "2002-12-18", "Новая Зеландия / США", 12, "movie", "main",
            "Братство расколото. Фродо и Сэм продолжают путь к Мордору.", "lotr_towers.jpg",
            "https://www.youtube.com/watch?v=LbfMDmc4azU", ["Фэнтези", "Приключения", "Боевик"], genres)
        
        chapters["lotr_3"] = self._create_chapter(
            franchises["lotr"], 3, "Возвращение короля", "2003-12-17", "Новая Зеландия / США", 12, "movie", "main",
            "Финальная битва за Средиземье.", "lotr_return.jpg",
            "https://www.youtube.com/watch?v=r5X-hFf6Bwo", ["Фэнтези", "Приключения", "Боевик"], genres)

        # Гарри Поттер
        chapters["hp_1"] = self._create_chapter(
            franchises["hp"], 1, "Гарри Поттер и философский камень", "2001-11-16", "Великобритания / США", 6, "movie", "main",
            "Одиннадцатилетний сирота узнаёт, что он волшебник.", "hp1.jpg",
            "https://www.youtube.com/watch?v=VyHV0BRtdxo", ["Фэнтези", "Приключения", "Семейный"], genres)
        
        chapters["hp_2"] = self._create_chapter(
            franchises["hp"], 2, "Гарри Поттер и Тайная комната", "2002-11-15", "Великобритания / США", 6, "movie", "main",
            "В Хогвартсе происходят странные нападения.", "hp2.jpg",
            "https://www.youtube.com/watch?v=1bIj8b7fG6k", ["Фэнтези", "Приключения", "Семейный"], genres)
        
        chapters["hp_7"] = self._create_chapter(
            franchises["hp"], 7, "Гарри Поттер и Дары Смерти. Часть 1", "2010-11-19", "Великобритания / США", 12, "movie", "main",
            "Гарри, Рон и Гермиона отправляются на поиски крестражей.", "hp7_1.jpg",
            "https://www.youtube.com/watch?v=MxqsmsA8y5k", ["Фэнтези", "Приключения", "Мистика"], genres)
        
        chapters["hp_8"] = self._create_chapter(
            franchises["hp"], 8, "Гарри Поттер и Дары Смерти. Часть 2", "2011-07-15", "Великобритания / США", 12, "movie", "main",
            "Финальная битва за Хогвартс.", "hp7_2.jpg",
            "https://www.youtube.com/watch?v=5NYt1qirBWg", ["Фэнтези", "Приключения", "Боевик"], genres)

        # Пример сериала
        chapters["hp_series"] = self._create_chapter(
            franchises["hp"], 9, "Гарри Поттер: Возвращение в Хогвартс", "2024-01-01", "Великобритания", 12, "series", "spinoff",
            "Документально-игровой мини-сериал о создании франшизы.", "hp_reunion.jpg",
            "https://www.youtube.com/watch?v=example", ["Документальный", "Фэнтези"], genres)

        # Тёмный рыцарь
        chapters["tdk_1"] = self._create_chapter(
            franchises["tdk"], 1, "Бэтмен: Начало", "2005-06-15", "США / Великобритания", 12, "movie", "main",
            "Брюс Уэйн возвращается в Готэм и начинает борьбу с преступностью.", "batman_begins.jpg",
            "https://www.youtube.com/watch?v=neY2xVmOfUM", ["Боевик", "Криминал", "Драма"], genres)
        
        chapters["tdk_2"] = self._create_chapter(
            franchises["tdk"], 2, "Тёмный рыцарь", "2008-07-18", "США / Великобритания", 12, "movie", "main",
            "Готэм охватывает хаос, когда появляется загадочный преступник Джокер.", "dark_knight.jpg",
            "https://www.youtube.com/watch?v=EXeTwQWrcwY", ["Боевик", "Криминал", "Триллер"], genres)
        
        chapters["tdk_3"] = self._create_chapter(
            franchises["tdk"], 3, "Тёмный рыцарь: Возрождение легенды", "2012-07-20", "США / Великобритания", 12, "movie", "main",
            "Спустя 8 лет Брюс Уэйн вынужден снова надеть костюм.", "dark_knight_rises.jpg",
            "https://www.youtube.com/watch?v=g8evyE9TuYk", ["Боевик", "Драма", "Триллер"], genres)

        return chapters

    def _setup_episodes(self, chapters):
        """Создаёт эпизоды для глав"""
        def create_episode(ch, num, title, hours, mins, file, thumb, date_override=None):
            Episode.objects.get_or_create(
                chapter=ch, episode_number=num,
                defaults={
                    "title": title, "video_file": f"media/{file}",
                    "duration": datetime.timedelta(hours=hours, minutes=mins),
                    "release_date": date_override or ch.release_date,
                    "thumbnail_img": f"thumbs/{thumb}"
                }
            )

        # По 1 эпизоду на каждый фильм
        dur_map = {
            "lotr_1": (2, 58), "lotr_2": (2, 59), "lotr_3": (3, 21),
            "hp_1": (2, 32), "hp_2": (2, 41), "hp_7": (2, 26), "hp_8": (2, 10),
            "tdk_1": (2, 20), "tdk_2": (2, 32), "tdk_3": (2, 44)
        }
        for ch_key in ["lotr_1", "lotr_2", "lotr_3", "hp_1", "hp_2", "hp_7", "hp_8", "tdk_1", "tdk_2", "tdk_3"]:
            ch = chapters[ch_key]
            h, m = dur_map[ch_key]
            create_episode(ch, 1, f"{ch.title} (Полная версия)", h, m, f"{ch_key}.mp4", f"{ch_key}_thumb.jpg")

        # 2 эпизода для сериала
        ch_ser = chapters["hp_series"]
        create_episode(ch_ser, 1, "Часть 1: Начало пути", 1, 25, "hp_reunion_ep1.mp4", "hp_reunion_ep1.jpg", datetime.date(2024, 1, 1))
        create_episode(ch_ser, 2, "Часть 2: Наследие магии", 1, 30, "hp_reunion_ep2.mp4", "hp_reunion_ep2.jpg", datetime.date(2024, 1, 8))

        return Episode.objects.filter(chapter__in=chapters.values()).count()

    def _setup_roles(self, chapters, persons):
        """Создаёт связи персон с главами"""
        roles_data = {
            "lotr_1": [("director", "Питер_Джексон"), ("screenwriter", "Фрэн_Уолш"), ("screenwriter", "Филиппа_Бойенс"), ("actor", "Элайджа_Вуд"), ("actor", "Иэн_Маккеллен")],
            "lotr_2": [("director", "Питер_Джексон"), ("producer", "Фрэн_Уолш"), ("actor", "Вигго_Мортенсен"), ("actor", "Иэн_Маккеллен")],
            "lotr_3": [("director", "Питер_Джексон"), ("screenwriter", "Филиппа_Бойенс"), ("actor", "Элайджа_Вуд"), ("actor", "Вигго_Мортенсен"), ("editor", "Ли_Смит")],
            
            "hp_1": [("director", "Крис_Коламбус"), ("screenwriter", "Стив_Кловс"), ("producer", "Дэвид_Хейман"), ("actor", "Дэниел_Рэдклифф"), ("actor", "Эмма_Уотсон")],
            "hp_2": [("director", "Крис_Коламбус"), ("screenwriter", "Стив_Кловс"), ("producer", "Дэвид_Хейман"), ("actor", "Руперт_Гринт"), ("actor", "Эмма_Уотсон")],
            "hp_7": [("director", "Дэвид_Йейтс"), ("screenwriter", "Стив_Кловс"), ("producer", "Дэвид_Хейман"), ("actor", "Дэниел_Рэдклифф")],
            "hp_8": [("director", "Дэвид_Йейтс"), ("screenwriter", "Стив_Кловс"), ("producer", "Эмма_Томас"), ("actor", "Дэниел_Рэдклифф"), ("actor", "Эмма_Уотсон")],
            
            "tdk_1": [("director", "Кристофер_Нолан"), ("screenwriter", "Кристофер_Нолан"), ("producer", "Эмма_Томас"), ("actor", "Кристиан_Бейл"), ("actor", "Гэри_Олдман"), ("editor", "Ли_Смит")],
            "tdk_2": [("director", "Кристофер_Нолан"), ("screenwriter", "Джонатан_Нолан"), ("producer", "Эмма_Томас"), ("actor", "Кристиан_Бейл"), ("actor", "Хит_Леджер"), ("editor", "Ли_Смит")],
            "tdk_3": [("director", "Кристофер_Нолан"), ("screenwriter", "Джонатан_Нолан"), ("producer", "Эмма_Томас"), ("actor", "Кристиан_Бейл"), ("actor", "Гэри_Олдман"), ("editor", "Ли_Смит")],
        }

        created_roles = 0
        for ch_key, role_list in roles_data.items():
            ch = chapters[ch_key]
            for role, person_key in role_list:
                p = persons[person_key]
                ChapterPersonRole.objects.get_or_create(chapter=ch, person=p, role=role)
                created_roles += 1
        return created_roles