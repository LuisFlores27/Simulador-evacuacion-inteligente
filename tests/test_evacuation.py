import os
import unittest
from unittest.mock import patch

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from ai.client import AIResponseError, GenerativeAIClient
from emergency.application import apply_scenario
from emergency.scenario import EmergencyScenario
from evacuation.astar import AStar
from evacuation.grid import Grid
from evacuation.manager import EvacuationManager
from evacuation.person import Person


class ScenarioTests(unittest.TestCase):
    def test_scenario_validates_contract_and_translates_compass_exit(self):
        scenario = EmergencyScenario.from_dict({
            "emergency_type": "combinada",
            "zone": "Laboratorio",
            "people": 5,
            "blocked_exits": ["norte", "B"],
        })
        self.assertEqual(scenario.blocked_exits, ("C", "B"))
        self.assertEqual(len(scenario.zone_positions()), 24)

    def test_scenario_rejects_bad_fields_types_zones_and_exits(self):
        invalid = [
            {"emergency_type": "unknown", "zone": "Sala"},
            {"emergency_type": "incendio", "zone": "Hospital"},
            {"emergency_type": "incendio", "zone": "Sala", "people": True},
            {"emergency_type": "incendio", "zone": "Sala", "people": 25},
            {"emergency_type": "incendio", "zone": "Sala", "blocked_exits": "A"},
            {"emergency_type": "incendio", "zone": "Sala", "extra": "value"},
            {"emergency_type": "incendio"},
            {"emergency_type": "salida_bloqueada", "zone": "Sala"},
        ]
        for data in invalid:
            with self.subTest(data=data), self.assertRaises(ValueError):
                EmergencyScenario.from_dict(data)

    def test_emergency_application_marks_hazard_and_blocks_real_exit(self):
        grid = Grid(30, 18)
        grid.register_exit((15, 5), "C")
        grid.register_exit((15, 11), "D")
        scenario = EmergencyScenario(
            "incendio",
            "Laboratorio",
            people=2,
            blocked_exits=["norte"],
        )
        people = apply_scenario(grid, scenario, lambda count, _: [(1, 1), (2, 1)])
        self.assertEqual(grid.get_node(1, 1).node_type, "incendio")
        self.assertEqual(grid.blocked_exits, {(15, 5)})
        self.assertEqual(grid.get_exits(), [(15, 11)])
        self.assertEqual(len(people), 2)

    def test_danger_zone_is_costly_but_exit_blockage_does_not_add_a_hazard(self):
        grid = Grid(30, 18)
        grid.register_exit((29, 8), "B")
        people = apply_scenario(
            grid,
            EmergencyScenario("zona_peligrosa", "Aula 2", people=1),
            lambda count, _: [(16, 1)],
        )
        self.assertEqual(grid.get_node(16, 1).node_type, "peligro")
        self.assertEqual(len(people), 1)

        fresh_grid = Grid(30, 18)
        fresh_grid.register_exit((29, 8), "B")
        apply_scenario(
            fresh_grid,
            EmergencyScenario(
                "salida_bloqueada",
                "Aula 2",
                people=1,
                blocked_exits=["B"],
            ),
            lambda count, _: [(16, 1)],
        )
        self.assertEqual(fresh_grid.get_node(16, 1).node_type, "libre")
        self.assertEqual(fresh_grid.get_node(29, 8).node_type, "salida_bloqueada")


class RoutingAndStatisticsTests(unittest.TestCase):
    def test_astar_prefers_safe_alternative_to_costly_danger(self):
        grid = Grid(5, 3)
        grid.set_danger(2, 1)
        path = AStar(grid).find_path((0, 1), (4, 1))
        self.assertNotIn((2, 1), path)

    def test_blocked_exit_is_not_selected_and_alternative_is_used(self):
        grid = Grid(5, 3)
        grid.register_exit((0, 1), "A")
        grid.register_exit((4, 1), "B")
        grid.block_exit((0, 1))
        person = Person(1, (2, 1))
        manager = EvacuationManager(grid, [person])
        manager.calculate_routes()
        self.assertEqual(person.target_exit, (4, 1))
        self.assertNotIn((0, 1), person.route)

    def test_exit_usage_counts_only_people_who_arrived(self):
        grid = Grid(4, 2)
        grid.register_exit((3, 0), "A")
        first = Person(1, (0, 0))
        second = Person(2, (0, 1))
        manager = EvacuationManager(grid, [first, second])
        manager.calculate_routes()
        self.assertEqual(manager.get_exit_usage(), {(3, 0): 0})
        while not all(person.evacuated for person in (first, second)):
            manager.move_people()
        summary = manager.get_evacuation_summary()
        self.assertEqual(summary.exit_usage, {(3, 0): 2})
        self.assertEqual(summary.people_evacuated, 2)
        self.assertTrue(summary.complete)

    def test_usage_summary_includes_multiple_and_unused_exits(self):
        grid = Grid(7, 3)
        grid.register_exit((0, 1), "A")
        grid.register_exit((6, 1), "B")
        grid.register_exit((3, 0), "C")
        people = [Person(1, (1, 1)), Person(2, (5, 1))]
        manager = EvacuationManager(grid, people)
        manager.calculate_routes()
        while not manager.all_evacuated():
            manager.move_people()
        self.assertEqual(
            manager.get_exit_usage(),
            {(0, 1): 1, (6, 1): 1, (3, 0): 0},
        )

    def test_two_blocked_exits_leave_people_without_route_when_isolated(self):
        grid = Grid(5, 3)
        grid.register_exit((0, 1), "A")
        grid.register_exit((4, 1), "B")
        grid.register_exit((0, 0), "C")
        grid.register_exit((4, 2), "D")
        for position in ((1, 1), (3, 1), (2, 0), (2, 2)):
            grid.set_obstacle(*position)
        grid.block_exit((0, 1))
        grid.block_exit((4, 1))
        person = Person(1, (2, 1))
        manager = EvacuationManager(grid, [person])
        manager.calculate_routes()
        self.assertFalse(person.has_route())
        self.assertEqual(len(grid.get_exits()), 2)

    def test_two_blocked_exits_still_route_to_an_open_alternative(self):
        grid = Grid(7, 3)
        grid.register_exit((0, 1), "A")
        grid.register_exit((6, 1), "B")
        grid.register_exit((3, 0), "C")
        grid.register_exit((3, 2), "D")
        grid.block_exit((0, 1))
        grid.block_exit((6, 1))
        person = Person(1, (3, 1))
        manager = EvacuationManager(grid, [person])
        manager.calculate_routes()
        self.assertIn(person.target_exit, {(3, 0), (3, 2)})
        self.assertTrue(person.has_route())

    def test_no_route_is_finalized_as_partial_not_complete(self):
        grid = Grid(3, 3)
        grid.register_exit((0, 0), "A")
        for position in ((1, 0), (0, 1), (2, 1), (1, 2)):
            grid.set_obstacle(*position)
        person = Person(1, (1, 1))
        manager = EvacuationManager(grid, [person])
        manager.calculate_routes()
        summary = manager.get_evacuation_summary()
        self.assertTrue(summary.evacuation_finished)
        self.assertFalse(summary.complete)
        self.assertEqual(summary.people_not_evacuated, 1)
        self.assertEqual(summary.people_without_route, 1)
        self.assertEqual(summary.exit_usage, {(0, 0): 0})


class AIClientTests(unittest.TestCase):
    def test_client_extracts_controlled_json_from_configured_endpoint(self):
        class FakeResponse:
            ok = True

            def json(self):
                return {
                    "choices": [{
                        "message": {
                            "content": (
                                '```json\n{"emergency_type":"incendio",'
                                '"zone":"Laboratorio"}\n```'
                            )
                        }
                    }]
                }

        client = GenerativeAIClient(
            endpoint="https://example.invalid/chat",
            model="test-model",
            api_key="test-key",
        )
        with patch("ai.client.requests.post", return_value=FakeResponse()) as post:
            result = client.generate_scenario("Incendio en el laboratorio")
        self.assertEqual(result["zone"], "Laboratorio")
        self.assertEqual(
            post.call_args.kwargs["headers"]["Authorization"],
            "Bearer test-key",
        )

    def test_client_reports_timeout_without_exposing_credentials(self):
        client = GenerativeAIClient(
            endpoint="https://example.invalid/chat",
            model="test-model",
            api_key="secret-test-key",
        )
        with patch(
            "ai.client.requests.post",
            side_effect=__import__("requests").Timeout("timeout"),
        ):
            with self.assertRaises(AIResponseError) as error:
                client.generate_scenario("prueba")
        self.assertNotIn("secret-test-key", str(error.exception))

    def test_unconfigured_client_fails_without_network_access(self):
        client = GenerativeAIClient(endpoint="", model="", api_key="")
        with patch("ai.client.requests.post") as post:
            with self.assertRaises(RuntimeError):
                client.generate_scenario("prueba")
        post.assert_not_called()


class PygameIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_simulation_applies_new_scenario_and_draws_final_panel(self):
        from graphics.graficos import ANCHO, ALTO, Simulacion

        simulation = Simulacion()
        try:
            self.assertEqual(len(simulation.people), 24)
            self.assertEqual(len(simulation.grid.get_exits()), 2)
            simulation.aplicar_escenario(
                EmergencyScenario(
                    "incendio",
                    "Aula 2",
                    people=3,
                    blocked_exits=["A"],
                )
            )
            self.assertEqual(len(simulation.people), 3)
            self.assertEqual(len(simulation.grid.get_exits()), 3)
            self.assertEqual(simulation.tiempo, 0)
            screen = pygame.Surface((ANCHO, ALTO))
            simulation.dibujar(screen)
        finally:
            simulation.ai_executor.shutdown(wait=True, cancel_futures=True)

    def test_b_returns_to_start_screen_for_another_scenario(self):
        from graphics.graficos import Simulacion

        simulation = Simulacion()
        try:
            simulation.manejar_evento(
                pygame.event.Event(pygame.KEYDOWN, key=pygame.K_F1)
            )
            self.assertFalse(simulation.inicio_pendiente)

            simulation.manejar_evento(
                pygame.event.Event(pygame.KEYDOWN, key=pygame.K_b)
            )
            self.assertTrue(simulation.inicio_pendiente)
            self.assertTrue(simulation.input_mode)
            self.assertEqual(simulation.instruccion, "")

            simulation.manejar_evento(
                pygame.event.Event(pygame.KEYDOWN, key=pygame.K_F2)
            )
            self.assertFalse(simulation.inicio_pendiente)
            self.assertEqual(simulation.escenario.zone, "Aula 2")
        finally:
            pygame.key.stop_text_input()
            simulation.ai_executor.shutdown(wait=True, cancel_futures=True)

    def test_simulation_screen_does_not_open_instruction_entry(self):
        from graphics.graficos import Simulacion

        simulation = Simulacion()
        try:
            simulation.manejar_evento(
                pygame.event.Event(pygame.KEYDOWN, key=pygame.K_F1)
            )
            simulation.manejar_evento(
                pygame.event.Event(pygame.KEYDOWN, key=pygame.K_t)
            )
            self.assertFalse(simulation.input_mode)
            self.assertFalse(simulation.inicio_pendiente)
        finally:
            simulation.ai_executor.shutdown(wait=True, cancel_futures=True)

    def test_startup_prompt_accepts_instruction_and_local_shortcut(self):
        from graphics.graficos import Simulacion

        simulation = Simulacion()
        try:
            self.assertTrue(simulation.inicio_pendiente)
            self.assertEqual(len(simulation.people), 24)
            simulation.manejar_evento(
                pygame.event.Event(pygame.TEXTINPUT, text="20 personas")
            )
            self.assertTrue(simulation.input_mode)
            self.assertEqual(simulation.instruccion, "20 personas")

            simulation.manejar_evento(
                pygame.event.Event(pygame.KEYDOWN, key=pygame.K_F1)
            )
            self.assertFalse(simulation.input_mode)
            self.assertFalse(simulation.inicio_pendiente)
            self.assertEqual(simulation.escenario.zone, "Laboratorio")
            self.assertEqual(len(simulation.people), 24)
        finally:
            pygame.key.stop_text_input()
            simulation.ai_executor.shutdown(wait=True, cancel_futures=True)


if __name__ == "__main__":
    unittest.main()
