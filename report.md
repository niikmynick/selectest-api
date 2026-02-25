## отчёт по отладке приложения

автор: Кобик Никита Алексеевич 

этапы работы: 
1. анализ структуры проекта
   
2. проверка requirements.txt \
	**проблема:** странная строка `fastapi==999.0.0; python_version < "3.8"` \
	**решение:** заменить ее просто на зависимость `fastapi` для получения актуальной версии

3. проверка файлов dockerfile и docker compose \
	вроде выглядит адекватно, потом посмотрим при запуске
   
4. статический анализ кода 
	- **проблема:** в `main.py` обнаружены deprecated методы `on_event`
		```python
		@app.on_event("startup")
		async def on_startup() -> None:
			logger.info("Запуск приложения")
			await _run_parse_job()
			global _scheduler
			_scheduler = create_scheduler(_run_parse_job)
			_scheduler.start()
		
		
		@app.on_event("shutdown")
		async def on_shutdown() -> None:
			logger.info("Остановка приложения")
			if _scheduler:
				_scheduler.shutdown(wait=False)
		```
		**решение:** заменить на актуальный способ -- lifespan
		```python
		@asynccontextmanager
		async def lifespan(app: FastAPI):
		    logger.info("Запуск приложения")
		    await _run_parse_job()
		    scheduler = create_scheduler(_run_parse_job)
		    scheduler.start()
		    yield
		
		    logger.info("Остановка приложения")
		    scheduler.shutdown(wait=False)
		
		
		app = FastAPI(title="Selectel Vacancies API", lifespan=lifespan)
		app.include_router(api_router)
		```

   - **проблема:** в `core/config.py` поле url для обращений к бд определен как field, то есть требует ввода от пользователя, хотя значение определено в окружении
		```python
		database_url: str = Field(
			"postgresql+asyncpg://postgres:postgres@db:5432/postgres_typo",
			validation_alias="DATABSE_URL",
		)
		```
     	**решение:** заменить на обычное поле, получаемое из переменной окружения + стандартное значение
     	```python
		database_url: str = "postgresql+asyncpg://postgres:postgres@db:5432/postgres_typo"
		```
   
   - **проблема:** в `core/config.py` в стандартном значении поля url для обращений к бд очепятка `postgres_typo`
		```python
		database_url: str = "postgresql+asyncpg://postgres:postgres@db:5432/postgres_typo"
		```
		**решение:** заменить `postgres_typo` на `postgres`
		```python
		database_url: str = "postgresql+asyncpg://postgres:postgres@db:5432/postgres"
		```
   
   - **проблема:** в `services/scheduler.py` при добавлении задачи задается интервал в секундах, хотя планировалось в минутах
		```python
		scheduler.add_job(
			job,
			trigger="interval",
			seconds=settings.parse_schedule_minutes,
			coalesce=True,
			max_instances=1,
		)
		```
	    **решение:** заменить `seconds` на `minutes`
     	```python
		scheduler.add_job(
	        job,
	        trigger="interval",
	        minutes=settings.parse_schedule_minutes,
	        coalesce=True,
	        max_instances=1,
	    )
		```

   - **проблема:** в `services/parser.py` создавался клиент, но после выполнения запросов подключение не завершалось
		```python
		async def parse_and_store(session: AsyncSession) -> int:
		    logger.info("Старт парсинга вакансий")
		    created_total = 0
		
		    timeout = httpx.Timeout(10.0, read=20.0)
		    try:
		        client = httpx.AsyncClient(timeout=timeout)
		        page = 1
		        while True:
		            payload = await fetch_page(client, page)
		            parsed_payloads = []
		            for item in payload.items:
		                parsed_payloads.append(
		                    {
		                        "external_id": item.id,
		                        "title": item.title,
		                        "timetable_mode_name": item.timetable_mode.name,
		                        "tag_name": item.tag.name,
		                        "city_name": item.city.name.strip(),
		                        "published_at": item.published_at,
		                        "is_remote_available": item.is_remote_available,
		                        "is_hot": item.is_hot,
		                    }
		                )
		
		            created_count = await upsert_external_vacancies(session, parsed_payloads)
		            created_total += created_count
		
		            if page >= payload.page_count:
		                break
		            page += 1
		    except (httpx.RequestError, httpx.HTTPStatusError) as exc:
		        logger.exception("Ошибка парсинга вакансий: %s", exc)
		        return 0
		
		    logger.info("Парсинг завершен, новых вакансий: %s", created_total)
		    return created_total
		```
	    **решение:** добавить использование контекстного менеджера
     	```python
		async def parse_and_store(session: AsyncSession) -> int:
		    logger.info("Старт парсинга вакансий")
		    created_total = 0
		
		    timeout = httpx.Timeout(10.0, read=20.0)
		    try:
		        async with httpx.AsyncClient(timeout=timeout) as client:
		            page = 1
		            while True:
		                payload = await fetch_page(client, page)
		                parsed_payloads = []
		                for item in payload.items:
		                    parsed_payloads.append(
		                        {
		                            "external_id": item.id,
		                            "title": item.title,
		                            "timetable_mode_name": item.timetable_mode.name,
		                            "tag_name": item.tag.name,
		                            "city_name": item.city.name.strip(),
		                            "published_at": item.published_at,
		                            "is_remote_available": item.is_remote_available,
		                            "is_hot": item.is_hot,
		                        }
		                    )
		
		                created_count = await upsert_external_vacancies(session, parsed_payloads)
		                created_total += created_count
		
		                if page >= payload.page_count:
		                    break
		                page += 1
		    except (httpx.RequestError, httpx.HTTPStatusError) as exc:
		        logger.exception("Ошибка парсинга вакансий: %s", exc)
		        return 0
		
		    logger.info("Парсинг завершен, новых вакансий: %s", created_total)
		    return created_total
      	```
	- **проблема:** в `services/parser.py` url обращения лежит просто как переменная
		```python
		API_URL = "https://api.selectel.ru/proxy/public/employee/api/public/vacancies"
		
		async def fetch_page(client: httpx.AsyncClient, page: int) -> ExternalVacanciesResponse:
		    response = await client.get(
		        API_URL,
		        params={"per_page": 1000, "page": page},
		    )
		    response.raise_for_status()
		    return ExternalVacanciesResponse.model_validate(response.json())
		```
	    **решение:** перенести объявление url в переменные окружения и получать из settings
     	```python
	    response = await client.get(
	        settings.vacancies_api_url,
	        params={"per_page": 1000, "page": page},
	    )
      	```

5. проверка при запуске
   - **проблема:** в `services/parser.py` иногда может возникать ошибка `AttributeError` из-за обращения к None
		```python
		"city_name": item.city.name.strip(),
		```
	    **решение:** добавить проверку на None у поля `city`
     	```python
      	"city_name": item.city.name.strip() if item.city else None, # city может быть None
      	```

   - **проблема:** в `crud/vacancy.py` несостыковка по типу переменной `existing_ids`
		```python
		if external_ids:
			existing_result = await session.execute(
				select(Vacancy.external_id).where(Vacancy.external_id.in_(external_ids))
			)
			existing_ids = set(existing_result.scalars().all())
		else:
			existing_ids = {}
		```
	    **решение:** исправить везде не set
     	```python
	    if external_ids:
	        existing_result = await session.execute(
	            select(Vacancy.external_id).where(Vacancy.external_id.in_(external_ids))
	        )
	        existing_ids = set(existing_result.scalars().all())
	    else:
	        existing_ids = set()
      	```

после правок приложение успешно запустилось

<img width="354" height="94" alt="image" src="https://github.com/user-attachments/assets/315e6111-6ca0-4b6d-928b-034f5c448bbe" />

вакансии добавляются

<img width="1624" height="1061" alt="image" src="https://github.com/user-attachments/assets/e8c8bd3a-c565-4145-8d0a-1f096724d919" />

удаляются

<img width="1624" height="1061" alt="image" src="https://github.com/user-attachments/assets/1deaeaf0-3bcf-407f-b033-866f7e6d1c46" />

<img width="1624" height="1061" alt="image" src="https://github.com/user-attachments/assets/e15b8743-9c60-40bc-ae3c-3c08f7762c7f" />

фоновая задача парсера работает исправно

<img width="1240" height="510" alt="image" src="https://github.com/user-attachments/assets/174afedd-755c-493b-b3f7-795753123ab4" />

