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
            "floor": 2,
        })
        self.assertEqual(scenario.blocked_exits, ("C", "B"))
        self.assertEqual(scenario.floor, 2)
        self.assertEqual(len(scenario.zone_positions()), 24)
        self.assertTrue(all(y >= 18 for _, y in scenario.zone_positions()))

    def test_scenario_rejects_bad_fields_types_zones_and_exits(self):
        invalid = [
            {"emergency_type": "unknown", "zone": "Sala"},
            {"emergency_type": "incendio", "zone": "Hospital"},
            {"emergency_type": "incendio", "zone": "Sala", "people": True},
            {"emergency_type": "incendio", "zone": "Sala", "people": 81},
            {"emergency_type": "incendio", "zone": "Sala", "blocked_exits": "A"},
            {"emergency_type": "incendio", "zone": "Sala", "extra": "value"},
            {"emergency_type": "incendio"},
            {"emergency_type": "salida_bloqueada", "zone": "Sala"},
            {"emergency_type": "incendio", "zone": "Sala", "floor": 3},
            {"emergency_type": "incendio", "zone": "Sala", "floor": True},
        ]
        for data in invalid:
            with self.subTest(data=data), self.assertRaises(ValueError):
                EmergencyScenario.from_dict(data)

    def test_scenario_supports_earthquake_with_additional_danger_zones(self):
        grid = Grid(30, 18)
        scenario = EmergencyScenario.from_dict({
            "emergency_type": "terremoto",
            "zone": "Laboratorio",
            "floor": 1,
            "people": 1,
            "danger_zones": ["Aula 2", "Pasillo central"],
        })
        apply_scenario(
            grid,
            scenario,
            lambda *_: [(2, 2)],
        )
        self.assertEqual(grid.get_node(2, 2).node_type, "peligro")
        self.assertEqual(grid.get_node(16, 1).node_type, "peligro")
        self.assertEqual(grid.get_node(1, 6).node_type, "peligro")

    def test_danger_zones_can_target_both_floors_of_the_same_room(self):
        grid = Grid(30, 36)
        grid.floor_offsets = {1: 18, 2: 0}
        scenario = EmergencyScenario.from_dict({
            "emergency_type": "terremoto",
            "zone": "Laboratorio",
            "floor": 1,
            "people": 1,
            "danger_zones": [
                {"zone": "Laboratorio", "floor": 2},
            ],
        })
        apply_scenario(grid, scenario, lambda *_: [(2, 19)])
        self.assertEqual(grid.get_node(2, 1).node_type, "peligro")
        self.assertEqual(grid.get_node(2, 19).node_type, "peligro")
        self.assertEqual(grid.get_node(16, 1).node_type, "libre")

    def test_scenario_accepts_person_counts_per_floor(self):
        scenario = EmergencyScenario.from_dict({
            "emergency_type": "incendio",
            "zone": "Laboratorio",
            "floor": 2,
            "people_by_floor": {"1": 8, "2": 4},
        })
        self.assertEqual(scenario.people, 12)
        self.assertEqual(scenario.people_by_floor, {1: 8, 2: 4})
        self.assertTrue(all(y >= 18 for _, y in scenario.zone_positions()))

        invalid = [
            {"1": 0, "2": 0},
            {"1": 80, "2": 1},
            {"1": 81, "2": 0},
            {"1": True, "2": 2},
            {"1": 2, "3": 2},
        ]
        for counts in invalid:
            with self.subTest(counts=counts), self.assertRaises(ValueError):
                EmergencyScenario.from_dict({
                    "emergency_type": "incendio",
                    "zone": "Laboratorio",
                    "people_by_floor": counts,
                })

    def test_scenario_accepts_up_to_80_people_and_rejects_81(self):
        scenario = EmergencyScenario.from_dict({
            "emergency_type": "incendio",
            "zone": "Laboratorio",
            "people": 80,
        })
        self.assertEqual(scenario.people, 80)

        with self.assertRaises(ValueError):
            EmergencyScenario.from_dict({
                "emergency_type": "incendio",
                "zone": "Laboratorio",
                "people": 81,
            })

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
        people = apply_scenario(grid, scenario, lambda *_: [(1, 1), (2, 1)])
        self.assertEqual(grid.get_node(1, 1).node_type, "incendio")
        self.assertEqual(grid.blocked_exits, {(15, 5)})
        self.assertEqual(grid.get_exits(), [(15, 11)])
        self.assertEqual(len(people), 2)

    def test_additional_danger_zones_remain_dangerous_in_fire_scenarios(self):
        grid = Grid(30, 18)
        scenario = EmergencyScenario(
            "incendio",
            "Laboratorio",
            people=1,
            danger_zones=["Aula 2"],
        )
        apply_scenario(grid, scenario, lambda *_: [(1, 1)])
        self.assertEqual(grid.get_node(1, 1).node_type, "incendio")
        self.assertEqual(grid.get_node(16, 1).node_type, "peligro")

    def test_danger_zone_is_costly_but_exit_blockage_does_not_add_a_hazard(self):
        grid = Grid(30, 18)
        grid.register_exit((29, 8), "B")
        people = apply_scenario(
            grid,
            EmergencyScenario("zona_peligrosa", "Aula 2", people=1),
            lambda *_: [(16, 1)],
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
            lambda *_: [(16, 1)],
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
    def test_client_defaults_to_local_ollama_when_environment_is_unset(self):
        with patch.dict(
            os.environ,
            {
                "GENAI_API_URL": "",
                "GENAI_MODEL": "",
                "GENAI_API_KEY": "",
            },
        ):
            client = GenerativeAIClient()

        self.assertEqual(
            client.endpoint,
            "http://localhost:11434/v1/chat/completions",
        )
        self.assertEqual(client.model, "llama3.2")
        self.assertTrue(client.is_configured)

    def test_instruction_validation_rejects_text_without_an_emergency(self):
        client = GenerativeAIClient()
        with patch("ai.client.requests.post") as post:
            with self.assertRaisesRegex(ValueError, "no describe una emergencia"):
                client.generate_scenario(".")
        post.assert_not_called()

    def test_instruction_validation_accepts_emergency_descriptions(self):
        for instruction in (
            "Genera un terremoto en el laboratorio",
            "Hay humo en el segundo piso",
            "Bloquea la salida norte",
        ):
            with self.subTest(instruction=instruction):
                GenerativeAIClient.validate_instruction(instruction)

    def test_client_extracts_controlled_json_from_configured_endpoint(self):
        class FakeResponse:
            ok = True

            def json(self):
                return {
                    "choices": [{
                        "message": {
                            "content": (
                                '```json\n{"emergency_type":"incendio",'
                                '"zone":"Laboratorio","floor":2}\n```'
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
        self.assertEqual(result["floor"], 2)
        self.assertEqual(
            post.call_args.kwargs["headers"]["Authorization"],
            "Bearer test-key",
        )

    def test_client_supports_local_endpoint_without_api_key(self):
        class FakeResponse:
            ok = True

            def json(self):
                return {
                    "choices": [{
                        "message": {
                            "content": '{"emergency_type":"incendio","zone":"Sala"}'
                        }
                    }]
                }

        client = GenerativeAIClient(
            endpoint="http://localhost:11434/v1/chat/completions",
            model="llama3.2",
            api_key="",
        )
        with patch("ai.client.requests.post", return_value=FakeResponse()) as post:
            result = client.generate_scenario("Incendio en la sala")

        self.assertEqual(result["zone"], "Sala")
        self.assertNotIn("Authorization", post.call_args.kwargs["headers"])

    def test_unspecified_people_count_uses_safe_default_instead_of_model_guess(self):
        class FakeResponse:
            ok = True

            def json(self):
                return {
                    "choices": [{
                        "message": {
                            "content": (
                                '{"emergency_type":"incendio",'
                                '"zone":"Laboratorio","floor":2,'
                                '"people":800,"people_by_floor":'
                                '{"1":100,"2":700}}'
                            )
                        }
                    }]
                }

        client = GenerativeAIClient()
        with patch("ai.client.requests.post", return_value=FakeResponse()):
            result = client.generate_scenario(
                "Simula un incendio en el laboratorio del segundo piso"
            )

        scenario = EmergencyScenario.from_dict(result)
        self.assertEqual(scenario.people, 24)
        self.assertIsNone(scenario.people_by_floor)
        self.assertTrue(client._instruction_specifies_people("8 personas"))
        self.assertTrue(
            client._instruction_specifies_people(
                "8 en el segundo piso y 4 en el primero"
            )
        )
        self.assertFalse(
            client._instruction_specifies_people(
                "Incendio en el segundo piso"
            )
        )

    def test_explicit_people_counts_by_floor_override_model_counts(self):
        class FakeResponse:
            ok = True

            def json(self):
                return {
                    "choices": [{
                        "message": {
                            "content": (
                                '{"emergency_type":"incendio","zone":"Laboratorio",'
                                '"floor":2,"people_by_floor":{"1":4,"2":8}}'
                            )
                        }
                    }]
                }

        client = GenerativeAIClient(
            endpoint="http://localhost:11434/v1/chat/completions",
            model="llama3.2",
        )
        with patch("ai.client.requests.post", return_value=FakeResponse()):
            result = client.generate_scenario(
                "Incendio en el segundo piso, 4 personas en el segundo piso "
                "y 8 personas en el primero"
            )
        self.assertEqual(result["people_by_floor"], {"1": 8, "2": 4})
        self.assertEqual(
            client._explicit_floor_counts(
                "segundo piso con 4 personas y primer piso con 8 personas"
            ),
            {"1": 8, "2": 4},
        )

    def test_earthquake_instruction_sets_earthquake_scenario_type(self):
        class FakeResponse:
            ok = True

            def json(self):
                return {
                    "choices": [{
                        "message": {
                            "content": (
                                '{"emergency_type":"combinada",'
                                '"zone":"Laboratorio","floor":1,'
                                '"blocked_exits":["norte","sur"],'
                                '"danger_zones":["Aula 2"]}'
                            )
                        }
                    }]
                }

        client = GenerativeAIClient(
            endpoint="http://localhost:11434/v1/chat/completions",
            model="llama3.2",
        )
        with patch("ai.client.requests.post", return_value=FakeResponse()):
            result = client.generate_scenario(
                "Genera un terremoto: los laborios del priumer y "
                "segundo piso eran peligros"
            )
        self.assertEqual(result["emergency_type"], "terremoto")
        self.assertEqual(result["zone"], "Laboratorio")
        self.assertEqual(result["floor"], 1)
        self.assertEqual(
            result["danger_zones"],
            [{"zone": "Laboratorio", "floor": 2}],
        )
        self.assertNotIn("blocked_exits", result)

    def test_fire_covering_an_entire_floor_marks_every_zone_as_fire(self):
        instruction = "Simula un incendio en todo el segundo piso"

        class FakeResponse:
            ok = True

            def json(self):
                return {
                    "choices": [{
                        "message": {
                            "content": (
                                '{"emergency_type":"incendio",'
                                '"zone":"Laboratorio","floor":2,"people":1}'
                            )
                        }
                    }]
                }

        client = GenerativeAIClient()
        with patch("ai.client.requests.post", return_value=FakeResponse()):
            scenario_data = client.generate_scenario(instruction)

        self.assertEqual(scenario_data["emergency_type"], "incendio")
        self.assertEqual(scenario_data["floor"], 2)
        self.assertEqual(len(scenario_data["fire_zones"]), 9)
        self.assertTrue(
            all(zone["floor"] == 2 for zone in scenario_data["fire_zones"])
        )

        scenario = EmergencyScenario.from_dict(scenario_data)
        grid = Grid(30, 36)
        grid.floor_offsets = {1: 18, 2: 0}
        grid.exit_offset_y = 18
        apply_scenario(
            grid,
            scenario,
            lambda *_: [
                (x, y)
                for y in range(19, 23)
                for x in range(1, 7)
            ],
        )
        affected_positions = {
            (
                x,
                y - 18 if floor == 2 else y + 18,
            )
            for zone, floor in scenario.fire_zones
            for x, y in scenario.positions_for_zone(zone, floor)
        }
        self.assertTrue(
            all(
                grid.get_node(x, y).node_type == "incendio"
                for x, y in affected_positions
            )
        )
        self.assertEqual(grid.get_node(1, 19).node_type, "libre")

    def test_full_floor_fire_instruction_can_target_both_floors(self):
        fire_zones = GenerativeAIClient._explicit_full_floor_fire_zones(
            "Incendio en ambos pisos completos"
        )
        self.assertEqual(len(fire_zones), 18)
        self.assertEqual(
            {zone["floor"] for zone in fire_zones},
            {1, 2},
        )

    def test_full_floor_fire_parser_handles_common_wording_without_extra_floors(self):
        examples = (
            ("Fuego en el piso 2 completo", {2}),
            ("Incendio en primer piso completo", {1}),
            ("Incendio en todo el segundo piso y humo en el primero", {2}),
            ("Incendio en todos los pisos", {1, 2}),
        )
        for instruction, expected_floors in examples:
            with self.subTest(instruction=instruction):
                fire_zones = GenerativeAIClient._explicit_full_floor_fire_zones(
                    instruction
                )
                self.assertEqual(
                    {zone["floor"] for zone in fire_zones},
                    expected_floors,
                )
                self.assertEqual(len(fire_zones), 9 * len(expected_floors))

    def test_exit_blocking_is_kept_only_when_requested(self):
        should_keep = GenerativeAIClient._explicitly_requests_blocked_exits(
            "Terremoto y bloquea la salida norte"
        )
        should_ignore = GenerativeAIClient._explicitly_requests_blocked_exits(
            "Terremoto en el laboratorio, ambos pisos peligrosos"
        )
        self.assertTrue(should_keep)
        self.assertFalse(should_ignore)

    def test_only_open_exit_instruction_resolves_all_other_exits_as_blocked(self):
        instruction = (
            "Simula un terremoto, genera 4 personas en el segundo piso y 4 "
            "en el primero, marca como peligro ambos laboratorios, es decir, "
            "los del segundo y primer piso, deja abierta solo la salida norte"
        )

        class FakeResponse:
            ok = True

            def json(self):
                return {
                    "choices": [{
                        "message": {
                            "content": (
                                '{"emergency_type":"terremoto",'
                                '"zone":"Laboratorio","floor":1,'
                                '"people_by_floor":{"1":4,"2":4},'
                                '"danger_zones":[],"blocked_exits":["B"]}'
                            )
                        }
                    }]
                }

        client = GenerativeAIClient()
        with patch("ai.client.requests.post", return_value=FakeResponse()):
            scenario = EmergencyScenario.from_dict(
                client.generate_scenario(instruction)
            )

        self.assertEqual(scenario.blocked_exits, ("A", "B", "D"))
        self.assertEqual(scenario.people_by_floor, {1: 4, 2: 4})
        self.assertEqual(scenario.zone, "Laboratorio")
        self.assertEqual(scenario.floor, 1)
        self.assertEqual(
            scenario.danger_zones,
            (("laboratorio", 2),),
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
        ) as post:
            with self.assertRaises(AIResponseError) as error:
                client.generate_scenario("Incendio en el laboratorio")
        self.assertEqual(post.call_args.kwargs["timeout"], 120)
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

    def test_map_labels_match_visual_floor_order(self):
        from graphics.graficos import ANCHO, ALTO, Edificio

        building = Edificio()
        rendered_labels = []

        class RecordingFont:
            def render(self, text, *_):
                rendered_labels.append(text)
                return pygame.Surface((1, 1))

        building.fuente_piso = RecordingFont()
        building.dibujar(pygame.Surface((ANCHO, ALTO)), 0)
        self.assertEqual(rendered_labels, ["PISO 2", "PISO 1"])

    def test_second_floor_evacuation_uses_stairs_and_first_floor_exits(self):
        from graphics.graficos import FLOOR_HEIGHT, STAIR_X, Simulacion

        simulation = Simulacion()
        try:
            simulation.aplicar_escenario(
                EmergencyScenario("incendio", "Laboratorio", people=1, floor=2)
            )
            person = simulation.people[0]
            self.assertLess(person.position[1], FLOOR_HEIGHT)
            self.assertGreaterEqual(person.target_exit[1], FLOOR_HEIGHT)
            self.assertTrue(
                any(
                    {start, end}
                    == {
                        (STAIR_X, FLOOR_HEIGHT - 1),
                        (STAIR_X, FLOOR_HEIGHT),
                    }
                    for start, end in zip(person.route, person.route[1:])
                )
            )
            stair_route = simulation.grid.stair_route
            stair_start = person.route.index(stair_route[0])
            self.assertEqual(
                person.route[stair_start:stair_start + len(stair_route)],
                stair_route,
            )
            self.assertEqual(
                simulation.grid.get_node(1, 1).node_type,
                "incendio",
            )
            self.assertEqual(simulation.grid.height, FLOOR_HEIGHT * 2)
            self.assertTrue(
                all(y >= FLOOR_HEIGHT for _, y in simulation.grid.get_exits())
            )
        finally:
            simulation.ai_executor.shutdown(wait=True, cancel_futures=True)

    def test_second_floor_route_reaches_exit_c_from_stair_landing(self):
        from graphics.graficos import Simulacion

        simulation = Simulacion()
        try:
            simulation.aplicar_escenario(
                EmergencyScenario(
                    "incendio",
                    "Laboratorio",
                    people=1,
                    floor=2,
                )
            )
            exit_c = next(
                position
                for position, identifier in simulation.grid.exits.items()
                if identifier == "C"
            )
            for position in simulation.grid.exits:
                if position != exit_c:
                    simulation.grid.block_exit(position)
            simulation.manager.calculate_routes()

            person = simulation.people[0]
            stair_route = simulation.grid.stair_route
            stair_start = person.route.index(stair_route[0])
            stair_end = stair_start + len(stair_route)
            self.assertEqual(person.target_exit, exit_c)
            self.assertEqual(
                person.route[stair_start:stair_end],
                stair_route,
            )
            self.assertEqual(
                person.route[stair_end:stair_end + 2],
                [simulation.grid.stair_exit_landing, exit_c],
            )
            self.assertNotEqual(
                person.route[stair_end],
                stair_route[-2],
            )
        finally:
            simulation.ai_executor.shutdown(wait=True, cancel_futures=True)

    def test_first_floor_routes_to_exit_c_do_not_cross_the_stairs(self):
        from graphics.graficos import FLOOR_HEIGHT, Simulacion

        simulation = Simulacion()
        try:
            simulation.aplicar_escenario(
                EmergencyScenario(
                    "incendio",
                    "Laboratorio",
                    people=20,
                    floor=1,
                )
            )
            exit_c = next(
                position
                for position, identifier in simulation.grid.exits.items()
                if identifier == "C"
            )
            for position in simulation.grid.exits:
                if position != exit_c:
                    simulation.grid.block_exit(position)
            simulation.manager.calculate_routes()

            first_floor_stairs = {
                position
                for position in simulation.grid.stair_route
                if position[1] >= FLOOR_HEIGHT
            }
            landing = simulation.grid.stair_exit_landing
            for person in simulation.people:
                with self.subTest(start=person.position):
                    self.assertEqual(person.target_exit, exit_c)
                    self.assertFalse(first_floor_stairs.intersection(person.route))
                    self.assertEqual(person.route[-2], landing)
        finally:
            simulation.ai_executor.shutdown(wait=True, cancel_futures=True)

    def test_people_requested_by_floor_are_placed_on_each_floor(self):
        from graphics.graficos import (
            ESCALERA,
            FLOOR_HEIGHT,
            PARED,
            Simulacion,
        )

        simulation = Simulacion()
        try:
            simulation.aplicar_escenario(
                EmergencyScenario(
                    "incendio",
                    "Laboratorio",
                    floor=2,
                    people_by_floor={"1": 8, "2": 4},
                )
            )
            first_floor = sum(
                person.position[1] >= FLOOR_HEIGHT
                for person in simulation.people
            )
            second_floor = sum(
                person.position[1] < FLOOR_HEIGHT
                for person in simulation.people
            )
            self.assertEqual((first_floor, second_floor), (8, 4))
            self.assertEqual(simulation.people_per_floor, {1: 8, 2: 4})
            for person in simulation.people:
                self.assertTrue(person.route)
                self.assertTrue(
                    all(
                        simulation.edificio.mapa[y][x] != PARED
                        for x, y in person.route
                    )
                )
                if person.position[1] < FLOOR_HEIGHT:
                    self.assertTrue(
                        any(
                            simulation.edificio.mapa[y][x] == ESCALERA
                            for x, y in person.route
                        )
                    )
        finally:
            simulation.ai_executor.shutdown(wait=True, cancel_futures=True)

    def test_second_floor_rooms_reach_the_stairs_without_wall_cells(self):
        from graphics.graficos import (
            ESCALERA,
            FLOOR_HEIGHT,
            HABITACIONES,
            PARED,
            Simulacion,
        )

        simulation = Simulacion()
        try:
            for _, _, _, _, zone in HABITACIONES:
                with self.subTest(zone=zone):
                    simulation.aplicar_escenario(
                        EmergencyScenario(
                            "incendio",
                            zone,
                            people=1,
                            floor=2,
                        )
                    )
                    person = simulation.people[0]
                    self.assertTrue(person.route)
                    self.assertTrue(
                        all(
                            simulation.edificio.mapa[y][x] != PARED
                            for x, y in person.route
                        )
                    )
                    self.assertTrue(
                        any(
                            simulation.edificio.mapa[y][x] == ESCALERA
                            for x, y in person.route
                        )
                    )
                    stair_route = simulation.grid.stair_route
                    stair_start = person.route.index(stair_route[0])
                    self.assertEqual(
                        person.route[
                            stair_start:stair_start + len(stair_route)
                        ],
                        stair_route,
                    )
                    self.assertFalse(
                        any(
                            simulation.edificio.mapa[y][x] == ESCALERA
                            for x, y in person.route[:stair_start]
                        )
                    )
                    self.assertGreaterEqual(person.target_exit[1], FLOOR_HEIGHT)
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

    def test_startup_screen_shows_loading_text_while_ai_request_is_pending(self):
        from graphics.graficos import ALTO, ANCHO, Simulacion

        simulation = Simulacion()
        try:
            simulation.ai_future = object()
            screen = pygame.Surface((ANCHO, ALTO))
            simulation.dibujar(screen)
            loading_area = screen.subsurface((20, 258, 420, 34))
            self.assertTrue(
                any(
                    loading_area.get_at((x, y))[:3] != (20, 20, 25)
                    for x in range(loading_area.get_width())
                    for y in range(loading_area.get_height())
                )
            )
        finally:
            simulation.ai_future = None
            pygame.key.stop_text_input()
            simulation.ai_executor.shutdown(wait=True, cancel_futures=True)

    def test_startup_screen_shows_ai_errors_after_failed_request(self):
        from graphics.graficos import ALTO, ANCHO, Simulacion

        class FailedFuture:
            def done(self):
                return True

            def result(self):
                raise AIResponseError("Ollama no responde")

        simulation = Simulacion()
        try:
            simulation.ai_future = FailedFuture()
            simulation.actualizar(0)
            self.assertTrue(simulation.input_mode)
            self.assertEqual(simulation.error_ia, "Ollama no responde")

            screen = pygame.Surface((ANCHO, ALTO))
            simulation.dibujar(screen)
            error_area = screen.subsurface((20, 258, 420, 34))
            self.assertTrue(
                any(
                    error_area.get_at((x, y))[:3] != (20, 20, 25)
                    for x in range(error_area.get_width())
                    for y in range(error_area.get_height())
                )
            )
        finally:
            simulation.ai_future = None
            pygame.key.stop_text_input()
            simulation.ai_executor.shutdown(wait=True, cancel_futures=True)

    def test_invalid_instruction_is_rejected_without_submitting_ai_request(self):
        from graphics.graficos import Simulacion

        simulation = Simulacion()
        try:
            simulation.instruccion = "."
            with patch.object(simulation.ai_client, "generate_scenario") as generate:
                simulation.enviar_instruccion()

            generate.assert_not_called()
            self.assertIsNone(simulation.ai_future)
            self.assertTrue(simulation.input_mode)
            self.assertEqual(simulation.instruccion, ".")
            self.assertIn("no describe una emergencia", simulation.error_ia)
        finally:
            pygame.key.stop_text_input()
            simulation.ai_executor.shutdown(wait=True, cancel_futures=True)

    def test_instruction_editor_supports_cursor_insertion_and_deletion(self):
        from graphics.graficos import ANCHO, ALTO, Simulacion

        simulation = Simulacion()
        try:
            simulation.manejar_evento(
                pygame.event.Event(pygame.TEXTINPUT, text="Incendio")
            )
            simulation.manejar_evento(
                pygame.event.Event(pygame.KEYDOWN, key=pygame.K_LEFT)
            )
            simulation.manejar_evento(
                pygame.event.Event(pygame.TEXTINPUT, text=" X")
            )
            self.assertEqual(simulation.instruccion, "Incendi Xo")

            simulation.manejar_evento(
                pygame.event.Event(pygame.KEYDOWN, key=pygame.K_HOME)
            )
            simulation.manejar_evento(
                pygame.event.Event(pygame.KEYDOWN, key=pygame.K_DELETE)
            )
            self.assertEqual(simulation.instruccion, "ncendi Xo")

            simulation.manejar_evento(
                pygame.event.Event(pygame.KEYDOWN, key=pygame.K_END)
            )
            simulation.manejar_evento(
                pygame.event.Event(pygame.KEYDOWN, key=pygame.K_BACKSPACE)
            )
            self.assertEqual(simulation.instruccion, "ncendi X")

            simulation.dibujar(pygame.Surface((ANCHO, ALTO)))
        finally:
            pygame.key.stop_text_input()
            simulation.ai_executor.shutdown(wait=True, cancel_futures=True)

    def test_instruction_editor_accepts_text_longer_than_180_characters(self):
        from graphics.graficos import Simulacion

        simulation = Simulacion()
        instruction = "terremoto " + ("zona peligrosa " * 20)
        try:
            simulation._replace_selection(instruction)
            self.assertEqual(simulation.instruccion, instruction)
            self.assertEqual(simulation.cursor_instruccion, len(instruction))

            simulation.cursor_instruccion = 5
            simulation._replace_selection("instrucción extensa ")
            expected = instruction[:5] + "instrucción extensa " + instruction[5:]
            self.assertEqual(simulation.instruccion, expected)
        finally:
            pygame.key.stop_text_input()
            simulation.ai_executor.shutdown(wait=True, cancel_futures=True)

    def test_instruction_wraps_into_visible_lines_and_resizes_the_field(self):
        from graphics.graficos import (
            ALTO,
            ANCHO,
            INSTRUCTION_MIN_HEIGHT,
            PREVIEW_BUTTON,
            Simulacion,
        )

        simulation = Simulacion()
        instruction = "Terremoto " + ("zona peligrosa en el laboratorio " * 12)
        try:
            simulation._replace_selection(instruction)
            font = pygame.font.SysFont("arial", 21)
            field, preview_button, wrapped_lines, _, _, _ = (
                simulation._prompt_layout(font)
            )

            self.assertGreater(len(wrapped_lines), 1)
            self.assertGreater(field.height, INSTRUCTION_MIN_HEIGHT)
            self.assertEqual(
                "".join(
                    instruction[start:end]
                    for start, end in wrapped_lines
                ),
                instruction,
            )
            self.assertGreater(preview_button.top, PREVIEW_BUTTON.top)
            simulation.dibujar(pygame.Surface((ANCHO, ALTO)))
        finally:
            pygame.key.stop_text_input()
            simulation.ai_executor.shutdown(wait=True, cancel_futures=True)

    def test_mouse_click_places_cursor_on_clicked_wrapped_text(self):
        from graphics.graficos import Simulacion

        simulation = Simulacion()
        instruction = "Terremoto " + ("zona peligrosa en el laboratorio " * 8)
        try:
            simulation._replace_selection(instruction)
            font = pygame.font.SysFont("arial", 21)
            field, _, lines, line_height, first_visible, _ = (
                simulation._prompt_layout(font)
            )
            target_line_index = first_visible
            start, end = lines[target_line_index]
            target_offset = min(5, end - start)
            click_position = (
                field.x + 12 + font.size(instruction[start:start + target_offset])[0],
                field.y + 8 + line_height // 2,
            )
            simulation.manejar_evento(
                pygame.event.Event(
                    pygame.MOUSEBUTTONDOWN,
                    button=1,
                    pos=click_position,
                    logical_pos=click_position,
                )
            )

            self.assertEqual(
                simulation.cursor_instruccion,
                start + target_offset,
            )
            self.assertIsNone(simulation.selection_anchor)
            self.assertTrue(simulation.input_mode)
        finally:
            pygame.key.stop_text_input()
            simulation.ai_executor.shutdown(wait=True, cancel_futures=True)

    def test_shift_enter_inserts_newline_without_submitting(self):
        from graphics.graficos import Simulacion

        simulation = Simulacion()
        try:
            simulation.manejar_evento(
                pygame.event.Event(pygame.TEXTINPUT, text="primera línea")
            )
            simulation.manejar_evento(
                pygame.event.Event(
                    pygame.KEYDOWN,
                    key=pygame.K_RETURN,
                    mod=pygame.KMOD_SHIFT,
                )
            )
            self.assertEqual(simulation.instruccion, "primera línea\n")
            self.assertIsNone(simulation.ai_future)
        finally:
            pygame.key.stop_text_input()
            simulation.ai_executor.shutdown(wait=True, cancel_futures=True)

    def test_instruction_editor_copies_and_pastes_with_clipboard(self):
        from graphics.graficos import Simulacion

        simulation = Simulacion()
        try:
            simulation.instruccion = "Incendio P2"
            simulation.cursor_instruccion = len(simulation.instruccion)
            with patch("pygame.scrap.get_init", return_value=True), patch(
                "pygame.scrap.put"
            ) as clipboard_put:
                simulation.manejar_evento(
                    pygame.event.Event(
                        pygame.KEYDOWN,
                        key=pygame.K_a,
                        mod=pygame.KMOD_CTRL,
                    )
                )
                simulation.manejar_evento(
                    pygame.event.Event(
                        pygame.KEYDOWN,
                        key=pygame.K_c,
                        mod=pygame.KMOD_CTRL,
                    )
                )
                clipboard_put.assert_called_with(
                    pygame.SCRAP_TEXT,
                    b"Incendio P2",
                )

            simulation.instruccion = ""
            simulation.cursor_instruccion = 0
            with patch("pygame.scrap.get_init", return_value=True), patch(
                "pygame.scrap.get",
                return_value=b"4 personas en el segundo piso\0",
            ):
                simulation.manejar_evento(
                    pygame.event.Event(
                        pygame.KEYDOWN,
                        key=pygame.K_v,
                        mod=pygame.KMOD_CTRL,
                    )
                )
            self.assertEqual(
                simulation.instruccion,
                "4 personas en el segundo piso",
            )
        finally:
            pygame.key.stop_text_input()
            simulation.ai_executor.shutdown(wait=True, cancel_futures=True)

    def test_preview_button_shows_clean_map_and_returns_to_prompt(self):
        from graphics.graficos import (
            ANCHO,
            ALTO,
            PREVIEW_BACK_BUTTON,
            PREVIEW_BUTTON,
            Simulacion,
        )

        simulation = Simulacion()
        try:
            simulation.manejar_evento(
                pygame.event.Event(
                    pygame.MOUSEBUTTONDOWN,
                    button=1,
                    pos=PREVIEW_BUTTON.center,
                    logical_pos=PREVIEW_BUTTON.center,
                )
            )
            self.assertTrue(simulation.preview_mode)
            self.assertIsNone(simulation.edificio_previsualizacion.grid)
            simulation.dibujar(pygame.Surface((ANCHO, ALTO)))
            simulation.manejar_evento(
                pygame.event.Event(
                    pygame.MOUSEBUTTONDOWN,
                    button=1,
                    pos=PREVIEW_BACK_BUTTON.center,
                    logical_pos=PREVIEW_BACK_BUTTON.center,
                )
            )
            self.assertFalse(simulation.preview_mode)
            self.assertTrue(simulation.input_mode)
        finally:
            pygame.key.stop_text_input()
            simulation.ai_executor.shutdown(wait=True, cancel_futures=True)

    def test_r_restarts_a_finished_simulation(self):
        from graphics.graficos import Simulacion

        simulation = Simulacion()
        try:
            simulation.aplicar_escenario(simulation.escenario)
            simulation.terminada = True
            simulation.tiempo = 30
            simulation.manejar_evento(
                pygame.event.Event(pygame.KEYDOWN, key=pygame.K_r)
            )
            self.assertFalse(simulation.terminada)
            self.assertEqual(simulation.tiempo, 0)
        finally:
            simulation.ai_executor.shutdown(wait=True, cancel_futures=True)

    def test_r_does_not_restart_simulation_while_it_is_running(self):
        from graphics.graficos import Simulacion

        simulation = Simulacion()
        try:
            simulation.aplicar_escenario(simulation.escenario)
            simulation.tiempo = 12
            simulation.manejar_evento(
                pygame.event.Event(pygame.KEYDOWN, key=pygame.K_r)
            )
            self.assertFalse(simulation.terminada)
            self.assertEqual(simulation.tiempo, 12)
        finally:
            simulation.ai_executor.shutdown(wait=True, cancel_futures=True)

    def test_simulation_panel_only_shows_evacuation_and_new_scenario_hint(self):
        from types import SimpleNamespace
        from graphics.graficos import ANCHO, ALTO, Simulacion

        simulation = Simulacion()
        rendered_text = []
        original_sysfont = pygame.font.SysFont

        class CapturingFont:
            def __init__(self, font):
                self.font = font

            def render(self, text, *args, **kwargs):
                rendered_text.append(text)
                return self.font.render(text, *args, **kwargs)

        try:
            summary = SimpleNamespace(
                people_evacuated=2,
                total_people=5,
                complete=False,
            )
            with patch.object(
                simulation.manager,
                "get_evacuation_summary",
                return_value=summary,
            ), patch(
                "graphics.graficos.pygame.font.SysFont",
                side_effect=lambda *args, **kwargs: CapturingFont(
                    original_sysfont(*args, **kwargs)
                ),
            ):
                simulation.dibujar_panel(pygame.Surface((ANCHO, ALTO)))

            self.assertIn("PERSONAS EVACUADAS", rendered_text)
            self.assertIn("2 / 5", rendered_text)
            self.assertIn("B: NUEVO ESCENARIO", rendered_text)
            self.assertNotIn("TIEMPO", rendered_text)
            self.assertNotIn("SALIDAS", rendered_text)
            self.assertNotIn("R: REINICIAR", rendered_text)

            rendered_text.clear()
            simulation.terminada = True
            summary.complete = True
            with patch.object(
                simulation.manager,
                "get_evacuation_summary",
                return_value=summary,
            ), patch(
                "graphics.graficos.pygame.font.SysFont",
                side_effect=lambda *args, **kwargs: CapturingFont(
                    original_sysfont(*args, **kwargs)
                ),
            ):
                simulation.dibujar_panel(pygame.Surface((ANCHO, ALTO)))

            self.assertIn("EVACUACIÓN COMPLETA", rendered_text)
            self.assertIn("R: REINICIAR", rendered_text)
            self.assertIn("B: NUEVO ESCENARIO", rendered_text)
        finally:
            simulation.ai_executor.shutdown(wait=True, cancel_futures=True)

    def test_earthquake_shakes_map_until_simulation_finishes(self):
        from graphics.graficos import Simulacion

        simulation = Simulacion()
        try:
            simulation.aplicar_escenario(
                EmergencyScenario(
                    "terremoto",
                    "Laboratorio",
                    people=1,
                )
            )
            simulation.tiempo = 0.1
            self.assertNotEqual(simulation.desplazamiento_terremoto(), (0, 0))
            simulation.terminada = True
            self.assertEqual(simulation.desplazamiento_terremoto(), (0, 0))
        finally:
            simulation.ai_executor.shutdown(wait=True, cancel_futures=True)


if __name__ == "__main__":
    unittest.main()
