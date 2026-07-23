import unittest

from app.main import app


class MutationResponseContractTests(unittest.TestCase):
    def setUp(self):
        self.schema = app.openapi()

    @staticmethod
    def _successful_response_schema(operation: dict) -> dict:
        response = next(
            response
            for status, response in operation["responses"].items()
            if status.startswith("2")
        )
        return response["content"]["application/json"]["schema"]

    def test_every_database_mutation_has_an_explicit_response_model(self):
        mutation_methods = {"post", "put", "patch", "delete"}
        read_only_operations = {
            ("post", "/api/campaigns/{campaign_id}/search"),
        }

        checked_operations = 0
        for path, operations in self.schema["paths"].items():
            for method in mutation_methods.intersection(operations):
                if (method, path) in read_only_operations:
                    continue

                response_schema = self._successful_response_schema(
                    operations[method]
                )
                self.assertIn(
                    "$ref",
                    response_schema,
                    f"{method.upper()} {path} has no response model",
                )
                checked_operations += 1

        self.assertGreater(checked_operations, 0)

    def test_every_api_operation_has_a_documented_response_schema(self):
        checked_operations = 0
        for path, operations in self.schema["paths"].items():
            for method, operation in operations.items():
                if method not in {
                    "get",
                    "post",
                    "put",
                    "patch",
                    "delete",
                }:
                    continue

                response_schema = self._successful_response_schema(
                    operation
                )
                self.assertTrue(
                    response_schema,
                    f"{method.upper()} {path} has no response schema",
                )
                checked_operations += 1

        self.assertGreater(checked_operations, 0)

    def test_domain_specific_mutation_envelopes_are_documented(self):
        paths = self.schema["paths"]

        character_delete = self._successful_response_schema(
            paths[
                "/api/campaigns/{campaign_id}/characters/{person_id}"
            ]["delete"]
        )
        roll_delete = self._successful_response_schema(
            paths[
                "/api/campaigns/{campaign_id}/rolls/sessions/{session_id}"
            ]["delete"]
        )

        self.assertEqual(
            "#/components/schemas/CharacterDeleteResponse",
            character_delete["$ref"],
        )
        self.assertEqual(
            "#/components/schemas/RollMutationResponse",
            roll_delete["$ref"],
        )


if __name__ == "__main__":
    unittest.main()
