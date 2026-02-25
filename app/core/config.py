from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # было postgres_typo вместо postgres
    # + это значение бралось из аргументов, а не из переменных окружения
    database_url: str = "postgresql+asyncpg://postgres:postgres@db:5432/postgres"
    log_level: str = "INFO"
    parse_schedule_minutes: int = 5

    # добавил url для получения вакансий сюда просто чтобы не было в исходном коде и можно было легко менять
    vacancies_api_url: str = "https://api.selectel.ru/proxy/public/employee/api/public/vacancies"


settings = Settings()
