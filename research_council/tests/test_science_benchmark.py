from research_council.schemas.models import ResearchPlan
from research_council.validation.benchmark import benchmark_hash, load_benchmark


def test_benchmark_questions_queries_and_provenance():
    benchmark = load_benchmark()
    assert len(benchmark.subquestions) == 10 and len(benchmark.perspectives) >= 14
    assert benchmark.queries() == benchmark.queries()
    assert len({query.family for query in benchmark.queries()}) >= 6
    assert all(query.provenance for query in benchmark.queries())
    plan = ResearchPlan(subquestions=benchmark.subquestions)
    assert (
        ResearchPlan.model_validate_json(plan.model_dump_json()).subquestions
        == benchmark.subquestions
    )
    assert len(benchmark_hash()) == 64


async def test_benchmark_planner_perspectives_and_queries(repository):
    from research_council.agents.contracts import PlanInput, QuestionInput
    from research_council.agents.perspective_generator import PerspectiveGenerator
    from research_council.agents.query_planner import QueryPlanner
    from research_council.agents.research_planner import ResearchPlanner
    from research_council.core.config import Settings
    from research_council.core.routing import ModelRouter
    from research_council.providers.fake import FakeProvider

    repo, run = repository
    settings = Settings(science_benchmark=load_benchmark().identifier)
    settings.research.max_queries = 40
    router = ModelRouter(settings, {"fake": FakeProvider()}, repo, run.run_id)
    plan = await ResearchPlanner(router).run(QuestionInput(task="Plan", question=run.question))
    value = PlanInput(task="Search", question=run.question, plan=plan)
    perspectives = await PerspectiveGenerator(router).run(value)
    queries = await QueryPlanner(router).run(value)
    assert len(plan.subquestions) == 10 and len(perspectives.perspectives) >= 14
    assert any(query.text == "sparse recovery FHSS" for query in queries.queries)
