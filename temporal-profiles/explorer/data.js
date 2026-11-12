window.TEMPORAL_EXPLORER_DATA = {
  "cases": [
    {
      "default_budget": null,
      "default_mode": "exact",
      "default_quota": 2,
      "default_target": 2,
      "description": "Two deletions have the same cost but leave different three-event counts.",
      "events": [
        {
          "cost": 1,
          "id": "a_early",
          "source": "leaf",
          "status": "optional",
          "target": "v",
          "time": 0
        },
        {
          "cost": 1,
          "id": "a_late",
          "source": "leaf",
          "status": "optional",
          "target": "v",
          "time": 2
        },
        {
          "cost": 1,
          "id": "b_early",
          "source": "v",
          "status": "keep",
          "target": "u",
          "time": 1
        },
        {
          "cost": 1,
          "id": "b_late",
          "source": "v",
          "status": "keep",
          "target": "u",
          "time": 3
        },
        {
          "cost": 1,
          "id": "c",
          "source": "u",
          "status": "keep",
          "target": "z",
          "time": 4
        }
      ],
      "id": "nonmonotone",
      "lesson": "Deleting a_late leaves W3 = 2; deleting a_early leaves W3 = 1. Both cost 1 and preserve W2 = 2. Only the first meets the exact target W3 = 2, while both satisfy W3 \u003c= 2.",
      "original": {
        "w2": 2,
        "w3": 3
      },
      "quotas": [
        {
          "R": 2,
          "baseline": {
            "w2": 2,
            "w3": 3
          },
          "forced_cost": 0,
          "min_w2": 0,
          "profiles": [
            {
              "deleted_ids": [
                "a_early",
                "a_late"
              ],
              "loss": 0,
              "optional_cost": 2,
              "total_cost": 2,
              "w2": 2,
              "w3": 0
            },
            {
              "deleted_ids": [
                "a_early"
              ],
              "loss": 0,
              "optional_cost": 1,
              "total_cost": 1,
              "w2": 2,
              "w3": 1
            },
            {
              "deleted_ids": [
                "a_late"
              ],
              "loss": 0,
              "optional_cost": 1,
              "total_cost": 1,
              "w2": 2,
              "w3": 2
            },
            {
              "deleted_ids": [],
              "loss": 0,
              "optional_cost": 0,
              "total_cost": 0,
              "w2": 2,
              "w3": 3
            }
          ],
          "status": "ok"
        },
        {
          "R": 1,
          "baseline": {
            "w2": 2,
            "w3": 3
          },
          "forced_cost": 0,
          "min_w2": 1,
          "profiles": [
            {
              "deleted_ids": [
                "a_early",
                "a_late"
              ],
              "loss": 0,
              "optional_cost": 2,
              "total_cost": 2,
              "w2": 2,
              "w3": 0
            },
            {
              "deleted_ids": [
                "a_early"
              ],
              "loss": 0,
              "optional_cost": 1,
              "total_cost": 1,
              "w2": 2,
              "w3": 1
            },
            {
              "deleted_ids": [
                "a_late"
              ],
              "loss": 0,
              "optional_cost": 1,
              "total_cost": 1,
              "w2": 2,
              "w3": 2
            },
            {
              "deleted_ids": [],
              "loss": 0,
              "optional_cost": 0,
              "total_cost": 0,
              "w2": 2,
              "w3": 3
            }
          ],
          "status": "ok"
        },
        {
          "R": 0,
          "baseline": {
            "w2": 2,
            "w3": 3
          },
          "forced_cost": 0,
          "min_w2": 2,
          "profiles": [
            {
              "deleted_ids": [
                "a_early",
                "a_late"
              ],
              "loss": 0,
              "optional_cost": 2,
              "total_cost": 2,
              "w2": 2,
              "w3": 0
            },
            {
              "deleted_ids": [
                "a_early"
              ],
              "loss": 0,
              "optional_cost": 1,
              "total_cost": 1,
              "w2": 2,
              "w3": 1
            },
            {
              "deleted_ids": [
                "a_late"
              ],
              "loss": 0,
              "optional_cost": 1,
              "total_cost": 1,
              "w2": 2,
              "w3": 2
            },
            {
              "deleted_ids": [],
              "loss": 0,
              "optional_cost": 0,
              "total_cost": 0,
              "w2": 2,
              "w3": 3
            }
          ],
          "status": "ok"
        }
      ],
      "root": "z",
      "source_path": "implementation/examples/nonmonotone.json",
      "title": "An exact target changes the choice",
      "verification": {
        "legal_subsets": 4,
        "profile_witnesses": 12,
        "quota_tables": 3
      }
    },
    {
      "default_budget": null,
      "default_mode": "exact",
      "default_quota": 1,
      "default_target": 1,
      "description": "Two early events have the same count effect but very different deletion costs.",
      "events": [
        {
          "cost": 100,
          "id": "a_early_expensive",
          "source": "leaf",
          "status": "optional",
          "target": "v",
          "time": 0
        },
        {
          "cost": 1,
          "id": "a_late_cheap",
          "source": "leaf",
          "status": "optional",
          "target": "v",
          "time": 2
        },
        {
          "cost": 1,
          "id": "b",
          "source": "v",
          "status": "keep",
          "target": "u",
          "time": 3
        },
        {
          "cost": 1,
          "id": "c",
          "source": "u",
          "status": "keep",
          "target": "z",
          "time": 4
        }
      ],
      "id": "weighted_a",
      "lesson": "Either optional A-event deletion leaves W3 = 1 and W2 = 1. The solver chooses a_late_cheap, which costs 1 instead of 100.",
      "original": {
        "w2": 1,
        "w3": 2
      },
      "quotas": [
        {
          "R": 1,
          "baseline": {
            "w2": 1,
            "w3": 2
          },
          "forced_cost": 0,
          "min_w2": 0,
          "profiles": [
            {
              "deleted_ids": [
                "a_early_expensive",
                "a_late_cheap"
              ],
              "loss": 0,
              "optional_cost": 101,
              "total_cost": 101,
              "w2": 1,
              "w3": 0
            },
            {
              "deleted_ids": [
                "a_late_cheap"
              ],
              "loss": 0,
              "optional_cost": 1,
              "total_cost": 1,
              "w2": 1,
              "w3": 1
            },
            {
              "deleted_ids": [],
              "loss": 0,
              "optional_cost": 0,
              "total_cost": 0,
              "w2": 1,
              "w3": 2
            }
          ],
          "status": "ok"
        },
        {
          "R": 0,
          "baseline": {
            "w2": 1,
            "w3": 2
          },
          "forced_cost": 0,
          "min_w2": 1,
          "profiles": [
            {
              "deleted_ids": [
                "a_early_expensive",
                "a_late_cheap"
              ],
              "loss": 0,
              "optional_cost": 101,
              "total_cost": 101,
              "w2": 1,
              "w3": 0
            },
            {
              "deleted_ids": [
                "a_late_cheap"
              ],
              "loss": 0,
              "optional_cost": 1,
              "total_cost": 1,
              "w2": 1,
              "w3": 1
            },
            {
              "deleted_ids": [],
              "loss": 0,
              "optional_cost": 0,
              "total_cost": 0,
              "w2": 1,
              "w3": 2
            }
          ],
          "status": "ok"
        }
      ],
      "root": "z",
      "source_path": "implementation/examples/weighted_a.json",
      "title": "The cheaper deletion wins",
      "verification": {
        "legal_subsets": 4,
        "profile_witnesses": 6,
        "quota_tables": 2
      }
    },
    {
      "default_budget": null,
      "default_mode": "exact",
      "default_quota": 2,
      "default_target": 3,
      "description": "Two parallel final events share a timestamp and contribute walks in blocks of two.",
      "events": [
        {
          "cost": 1,
          "id": "a",
          "source": "leaf",
          "status": "keep",
          "target": "v",
          "time": 0
        },
        {
          "cost": 1,
          "id": "b_early",
          "source": "v",
          "status": "keep",
          "target": "u",
          "time": 1
        },
        {
          "cost": 1,
          "id": "b_late",
          "source": "v",
          "status": "keep",
          "target": "u",
          "time": 3
        },
        {
          "cost": 100,
          "id": "c_first_expensive",
          "source": "u",
          "status": "optional",
          "target": "z",
          "time": 4
        },
        {
          "cost": 1,
          "id": "c_second_cheap",
          "source": "u",
          "status": "optional",
          "target": "z",
          "time": 4
        }
      ],
      "id": "weighted_c",
      "lesson": "With W2 >= 2, only W3 = 2 and W3 = 4 are attainable. An exact target of 3 is impossible at any cost, but the upper bound W3 \u003c= 3 is met by deleting c_second_cheap at cost 1. The parallel events keep distinct IDs.",
      "original": {
        "w2": 4,
        "w3": 4
      },
      "quotas": [
        {
          "R": 4,
          "baseline": {
            "w2": 4,
            "w3": 4
          },
          "forced_cost": 0,
          "min_w2": 0,
          "profiles": [
            {
              "deleted_ids": [],
              "loss": 0,
              "optional_cost": 0,
              "total_cost": 0,
              "w2": 4,
              "w3": 4
            },
            {
              "deleted_ids": [
                "c_second_cheap"
              ],
              "loss": 2,
              "optional_cost": 1,
              "total_cost": 1,
              "w2": 2,
              "w3": 2
            },
            {
              "deleted_ids": [
                "c_first_expensive",
                "c_second_cheap"
              ],
              "loss": 4,
              "optional_cost": 101,
              "total_cost": 101,
              "w2": 0,
              "w3": 0
            }
          ],
          "status": "ok"
        },
        {
          "R": 3,
          "baseline": {
            "w2": 4,
            "w3": 4
          },
          "forced_cost": 0,
          "min_w2": 1,
          "profiles": [
            {
              "deleted_ids": [],
              "loss": 0,
              "optional_cost": 0,
              "total_cost": 0,
              "w2": 4,
              "w3": 4
            },
            {
              "deleted_ids": [
                "c_second_cheap"
              ],
              "loss": 2,
              "optional_cost": 1,
              "total_cost": 1,
              "w2": 2,
              "w3": 2
            }
          ],
          "status": "ok"
        },
        {
          "R": 2,
          "baseline": {
            "w2": 4,
            "w3": 4
          },
          "forced_cost": 0,
          "min_w2": 2,
          "profiles": [
            {
              "deleted_ids": [],
              "loss": 0,
              "optional_cost": 0,
              "total_cost": 0,
              "w2": 4,
              "w3": 4
            },
            {
              "deleted_ids": [
                "c_second_cheap"
              ],
              "loss": 2,
              "optional_cost": 1,
              "total_cost": 1,
              "w2": 2,
              "w3": 2
            }
          ],
          "status": "ok"
        },
        {
          "R": 1,
          "baseline": {
            "w2": 4,
            "w3": 4
          },
          "forced_cost": 0,
          "min_w2": 3,
          "profiles": [
            {
              "deleted_ids": [],
              "loss": 0,
              "optional_cost": 0,
              "total_cost": 0,
              "w2": 4,
              "w3": 4
            }
          ],
          "status": "ok"
        },
        {
          "R": 0,
          "baseline": {
            "w2": 4,
            "w3": 4
          },
          "forced_cost": 0,
          "min_w2": 4,
          "profiles": [
            {
              "deleted_ids": [],
              "loss": 0,
              "optional_cost": 0,
              "total_cost": 0,
              "w2": 4,
              "w3": 4
            }
          ],
          "status": "ok"
        }
      ],
      "root": "z",
      "source_path": "implementation/examples/weighted_c.json",
      "title": "An exact count can be missing",
      "verification": {
        "legal_subsets": 4,
        "profile_witnesses": 9,
        "quota_tables": 5
      }
    },
    {
      "default_budget": null,
      "default_mode": "exact",
      "default_quota": 0,
      "default_target": 0,
      "description": "A required middle-event deletion removes both original walks and costs 7.",
      "events": [
        {
          "cost": 1,
          "id": "a",
          "source": "leaf",
          "status": "keep",
          "target": "v",
          "time": 0
        },
        {
          "cost": 7,
          "id": "b_forced",
          "source": "v",
          "status": "delete",
          "target": "u",
          "time": 1
        },
        {
          "cost": 3,
          "id": "c",
          "source": "u",
          "status": "optional",
          "target": "z",
          "time": 2
        }
      ],
      "id": "forced_baseline",
      "lesson": "The original counts are W2 = 1 and W3 = 1. Deleting b_forced is mandatory, so the baseline becomes (0, 0) and every allowed result costs at least 7. Requiring W2 >= 1 is infeasible even with an unlimited budget.",
      "original": {
        "w2": 1,
        "w3": 1
      },
      "quotas": [
        {
          "R": 0,
          "baseline": {
            "w2": 0,
            "w3": 0
          },
          "forced_cost": 7,
          "min_w2": 0,
          "profiles": [
            {
              "deleted_ids": [
                "b_forced"
              ],
              "loss": 0,
              "optional_cost": 0,
              "total_cost": 7,
              "w2": 0,
              "w3": 0
            }
          ],
          "status": "ok"
        },
        {
          "R": null,
          "baseline": {
            "w2": 0,
            "w3": 0
          },
          "forced_cost": 7,
          "min_w2": 1,
          "profiles": [],
          "status": "infeasible"
        }
      ],
      "root": "z",
      "source_path": "implementation/examples/forced_baseline.json",
      "title": "Mandatory deletions change the baseline",
      "verification": {
        "legal_subsets": 2,
        "profile_witnesses": 1,
        "quota_tables": 2
      }
    },
    {
      "default_budget": null,
      "default_mode": "exact",
      "default_quota": 5,
      "default_target": 1,
      "description": "Ten events combine four incoming paths and four final transactions toward one root.",
      "events": [
        {
          "cost": 1,
          "id": "A2",
          "source": "s2",
          "status": "optional",
          "target": "v2",
          "time": 1
        },
        {
          "cost": 1,
          "id": "A4",
          "source": "s4",
          "status": "optional",
          "target": "v4",
          "time": 1
        },
        {
          "cost": 1,
          "id": "B1",
          "source": "v1",
          "status": "keep",
          "target": "u",
          "time": 2
        },
        {
          "cost": 1,
          "id": "B2",
          "source": "v2",
          "status": "keep",
          "target": "u",
          "time": 4
        },
        {
          "cost": 1,
          "id": "B3",
          "source": "v3",
          "status": "keep",
          "target": "u",
          "time": 6
        },
        {
          "cost": 1,
          "id": "B4",
          "source": "v4",
          "status": "keep",
          "target": "u",
          "time": 8
        },
        {
          "cost": 1,
          "id": "C1",
          "source": "u",
          "status": "optional",
          "target": "z",
          "time": 3
        },
        {
          "cost": 1,
          "id": "C2",
          "source": "u",
          "status": "optional",
          "target": "z",
          "time": 5
        },
        {
          "cost": 1,
          "id": "C3",
          "source": "u",
          "status": "optional",
          "target": "z",
          "time": 7
        },
        {
          "cost": 1,
          "id": "C4",
          "source": "u",
          "status": "optional",
          "target": "z",
          "time": 9
        }
      ],
      "id": "illustration",
      "lesson": "The original counts are W2 = 10 and W3 = 4. With W2 >= 5, deleting A2 attains the exact target W3 = 1 at cost 1 while preserving W2 = 10. A lower quota permits extra loss; it does not require using that loss. Explore other quotas and targets to see the full minimum-cost table.",
      "original": {
        "w2": 10,
        "w3": 4
      },
      "quotas": [
        {
          "R": 10,
          "baseline": {
            "w2": 10,
            "w3": 4
          },
          "forced_cost": 0,
          "min_w2": 0,
          "profiles": [
            {
              "deleted_ids": [
                "A2",
                "A4"
              ],
              "loss": 0,
              "optional_cost": 2,
              "total_cost": 2,
              "w2": 10,
              "w3": 0
            },
            {
              "deleted_ids": [
                "A2"
              ],
              "loss": 0,
              "optional_cost": 1,
              "total_cost": 1,
              "w2": 10,
              "w3": 1
            },
            {
              "deleted_ids": [
                "A4"
              ],
              "loss": 0,
              "optional_cost": 1,
              "total_cost": 1,
              "w2": 10,
              "w3": 3
            },
            {
              "deleted_ids": [],
              "loss": 0,
              "optional_cost": 0,
              "total_cost": 0,
              "w2": 10,
              "w3": 4
            },
            {
              "deleted_ids": [
                "A2",
                "A4",
                "C1"
              ],
              "loss": 1,
              "optional_cost": 3,
              "total_cost": 3,
              "w2": 9,
              "w3": 0
            },
            {
              "deleted_ids": [
                "A2",
                "C1"
              ],
              "loss": 1,
              "optional_cost": 2,
              "total_cost": 2,
              "w2": 9,
              "w3": 1
            },
            {
              "deleted_ids": [
                "A4",
                "C1"
              ],
              "loss": 1,
              "optional_cost": 2,
              "total_cost": 2,
              "w2": 9,
              "w3": 3
            },
            {
              "deleted_ids": [
                "C1"
              ],
              "loss": 1,
              "optional_cost": 1,
              "total_cost": 1,
              "w2": 9,
              "w3": 4
            },
            {
              "deleted_ids": [
                "A2",
                "A4",
                "C2"
              ],
              "loss": 2,
              "optional_cost": 3,
              "total_cost": 3,
              "w2": 8,
              "w3": 0
            },
            {
              "deleted_ids": [
                "A2",
                "C2"
              ],
              "loss": 2,
              "optional_cost": 2,
              "total_cost": 2,
              "w2": 8,
              "w3": 1
            },
            {
              "deleted_ids": [
                "A4",
                "C2"
              ],
              "loss": 2,
              "optional_cost": 2,
              "total_cost": 2,
              "w2": 8,
              "w3": 2
            },
            {
              "deleted_ids": [
                "C2"
              ],
              "loss": 2,
              "optional_cost": 1,
              "total_cost": 1,
              "w2": 8,
              "w3": 3
            },
            {
              "deleted_ids": [
                "A2",
                "A4",
                "C3"
              ],
              "loss": 3,
              "optional_cost": 3,
              "total_cost": 3,
              "w2": 7,
              "w3": 0
            },
            {
              "deleted_ids": [
                "A2",
                "C3"
              ],
              "loss": 3,
              "optional_cost": 2,
              "total_cost": 2,
              "w2": 7,
              "w3": 1
            },
            {
              "deleted_ids": [
                "A4",
                "C3"
              ],
              "loss": 3,
              "optional_cost": 2,
              "total_cost": 2,
              "w2": 7,
              "w3": 2
            },
            {
              "deleted_ids": [
                "C3"
              ],
              "loss": 3,
              "optional_cost": 1,
              "total_cost": 1,
              "w2": 7,
              "w3": 3
            },
            {
              "deleted_ids": [
                "A2",
                "C4"
              ],
              "loss": 4,
              "optional_cost": 2,
              "total_cost": 2,
              "w2": 6,
              "w3": 0
            },
            {
              "deleted_ids": [
                "A2",
                "C1",
                "C3"
              ],
              "loss": 4,
              "optional_cost": 3,
              "total_cost": 3,
              "w2": 6,
              "w3": 1
            },
            {
              "deleted_ids": [
                "C4"
              ],
              "loss": 4,
              "optional_cost": 1,
              "total_cost": 1,
              "w2": 6,
              "w3": 2
            },
            {
              "deleted_ids": [
                "C1",
                "C3"
              ],
              "loss": 4,
              "optional_cost": 2,
              "total_cost": 2,
              "w2": 6,
              "w3": 3
            },
            {
              "deleted_ids": [
                "A2",
                "C1",
                "C4"
              ],
              "loss": 5,
              "optional_cost": 3,
              "total_cost": 3,
              "w2": 5,
              "w3": 0
            },
            {
              "deleted_ids": [
                "A4",
                "C2",
                "C3"
              ],
              "loss": 5,
              "optional_cost": 3,
              "total_cost": 3,
              "w2": 5,
              "w3": 1
            },
            {
              "deleted_ids": [
                "C2",
                "C3"
              ],
              "loss": 5,
              "optional_cost": 2,
              "total_cost": 2,
              "w2": 5,
              "w3": 2
            },
            {
              "deleted_ids": [
                "A2",
                "C2",
                "C4"
              ],
              "loss": 6,
              "optional_cost": 3,
              "total_cost": 3,
              "w2": 4,
              "w3": 0
            },
            {
              "deleted_ids": [
                "C2",
                "C4"
              ],
              "loss": 6,
              "optional_cost": 2,
              "total_cost": 2,
              "w2": 4,
              "w3": 1
            },
            {
              "deleted_ids": [
                "C1",
                "C2",
                "C3"
              ],
              "loss": 6,
              "optional_cost": 3,
              "total_cost": 3,
              "w2": 4,
              "w3": 2
            },
            {
              "deleted_ids": [
                "A2",
                "C3",
                "C4"
              ],
              "loss": 7,
              "optional_cost": 3,
              "total_cost": 3,
              "w2": 3,
              "w3": 0
            },
            {
              "deleted_ids": [
                "C3",
                "C4"
              ],
              "loss": 7,
              "optional_cost": 2,
              "total_cost": 2,
              "w2": 3,
              "w3": 1
            },
            {
              "deleted_ids": [
                "A2",
                "C1",
                "C3",
                "C4"
              ],
              "loss": 8,
              "optional_cost": 4,
              "total_cost": 4,
              "w2": 2,
              "w3": 0
            },
            {
              "deleted_ids": [
                "C1",
                "C3",
                "C4"
              ],
              "loss": 8,
              "optional_cost": 3,
              "total_cost": 3,
              "w2": 2,
              "w3": 1
            },
            {
              "deleted_ids": [
                "C2",
                "C3",
                "C4"
              ],
              "loss": 9,
              "optional_cost": 3,
              "total_cost": 3,
              "w2": 1,
              "w3": 0
            },
            {
              "deleted_ids": [
                "C1",
                "C2",
                "C3",
                "C4"
              ],
              "loss": 10,
              "optional_cost": 4,
              "total_cost": 4,
              "w2": 0,
              "w3": 0
            }
          ],
          "status": "ok"
        },
        {
          "R": 9,
          "baseline": {
            "w2": 10,
            "w3": 4
          },
          "forced_cost": 0,
          "min_w2": 1,
          "profiles": [
            {
              "deleted_ids": [
                "A2",
                "A4"
              ],
              "loss": 0,
              "optional_cost": 2,
              "total_cost": 2,
              "w2": 10,
              "w3": 0
            },
            {
              "deleted_ids": [
                "A2"
              ],
              "loss": 0,
              "optional_cost": 1,
              "total_cost": 1,
              "w2": 10,
              "w3": 1
            },
            {
              "deleted_ids": [
                "A4"
              ],
              "loss": 0,
              "optional_cost": 1,
              "total_cost": 1,
              "w2": 10,
              "w3": 3
            },
            {
              "deleted_ids": [],
              "loss": 0,
              "optional_cost": 0,
              "total_cost": 0,
              "w2": 10,
              "w3": 4
            },
            {
              "deleted_ids": [
                "A2",
                "A4",
                "C1"
              ],
              "loss": 1,
              "optional_cost": 3,
              "total_cost": 3,
              "w2": 9,
              "w3": 0
            },
            {
              "deleted_ids": [
                "A2",
                "C1"
              ],
              "loss": 1,
              "optional_cost": 2,
              "total_cost": 2,
              "w2": 9,
              "w3": 1
            },
            {
              "deleted_ids": [
                "A4",
                "C1"
              ],
              "loss": 1,
              "optional_cost": 2,
              "total_cost": 2,
              "w2": 9,
              "w3": 3
            },
            {
              "deleted_ids": [
                "C1"
              ],
              "loss": 1,
              "optional_cost": 1,
              "total_cost": 1,
              "w2": 9,
              "w3": 4
            },
            {
              "deleted_ids": [
                "A2",
                "A4",
                "C2"
              ],
              "loss": 2,
              "optional_cost": 3,
              "total_cost": 3,
              "w2": 8,
              "w3": 0
            },
            {
              "deleted_ids": [
                "A2",
                "C2"
              ],
              "loss": 2,
              "optional_cost": 2,
              "total_cost": 2,
              "w2": 8,
              "w3": 1
            },
            {
              "deleted_ids": [
                "A4",
                "C2"
              ],
              "loss": 2,
              "optional_cost": 2,
              "total_cost": 2,
              "w2": 8,
              "w3": 2
            },
            {
              "deleted_ids": [
                "C2"
              ],
              "loss": 2,
              "optional_cost": 1,
              "total_cost": 1,
              "w2": 8,
              "w3": 3
            },
            {
              "deleted_ids": [
                "A2",
                "A4",
                "C3"
              ],
              "loss": 3,
              "optional_cost": 3,
              "total_cost": 3,
              "w2": 7,
              "w3": 0
            },
            {
              "deleted_ids": [
                "A2",
                "C3"
              ],
              "loss": 3,
              "optional_cost": 2,
              "total_cost": 2,
              "w2": 7,
              "w3": 1
            },
            {
              "deleted_ids": [
                "A4",
                "C3"
              ],
              "loss": 3,
              "optional_cost": 2,
              "total_cost": 2,
              "w2": 7,
              "w3": 2
            },
            {
              "deleted_ids": [
                "C3"
              ],
              "loss": 3,
              "optional_cost": 1,
              "total_cost": 1,
              "w2": 7,
              "w3": 3
            },
            {
              "deleted_ids": [
                "A2",
                "C4"
              ],
              "loss": 4,
              "optional_cost": 2,
              "total_cost": 2,
              "w2": 6,
              "w3": 0
            },
            {
              "deleted_ids": [
                "A2",
                "C1",
                "C3"
              ],
              "loss": 4,
              "optional_cost": 3,
              "total_cost": 3,
              "w2": 6,
              "w3": 1
            },
            {
              "deleted_ids": [
                "C4"
              ],
              "loss": 4,
              "optional_cost": 1,
              "total_cost": 1,
              "w2": 6,
              "w3": 2
            },
            {
              "deleted_ids": [
                "C1",
                "C3"
              ],
              "loss": 4,
              "optional_cost": 2,
              "total_cost": 2,
              "w2": 6,
              "w3": 3
            },
            {
              "deleted_ids": [
                "A2",
                "C1",
                "C4"
              ],
              "loss": 5,
              "optional_cost": 3,
              "total_cost": 3,
              "w2": 5,
              "w3": 0
            },
            {
              "deleted_ids": [
                "A4",
                "C2",
                "C3"
              ],
              "loss": 5,
              "optional_cost": 3,
              "total_cost": 3,
              "w2": 5,
              "w3": 1
            },
            {
              "deleted_ids": [
                "C2",
                "C3"
              ],
              "loss": 5,
              "optional_cost": 2,
              "total_cost": 2,
              "w2": 5,
              "w3": 2
            },
            {
              "deleted_ids": [
                "A2",
                "C2",
                "C4"
              ],
              "loss": 6,
              "optional_cost": 3,
              "total_cost": 3,
              "w2": 4,
              "w3": 0
            },
            {
              "deleted_ids": [
                "C2",
                "C4"
              ],
              "loss": 6,
              "optional_cost": 2,
              "total_cost": 2,
              "w2": 4,
              "w3": 1
            },
            {
              "deleted_ids": [
                "C1",
                "C2",
                "C3"
              ],
              "loss": 6,
              "optional_cost": 3,
              "total_cost": 3,
              "w2": 4,
              "w3": 2
            },
            {
              "deleted_ids": [
                "A2",
                "C3",
                "C4"
              ],
              "loss": 7,
              "optional_cost": 3,
              "total_cost": 3,
              "w2": 3,
              "w3": 0
            },
            {
              "deleted_ids": [
                "C3",
                "C4"
              ],
              "loss": 7,
              "optional_cost": 2,
              "total_cost": 2,
              "w2": 3,
              "w3": 1
            },
            {
              "deleted_ids": [
                "A2",
                "C1",
                "C3",
                "C4"
              ],
              "loss": 8,
              "optional_cost": 4,
              "total_cost": 4,
              "w2": 2,
              "w3": 0
            },
            {
              "deleted_ids": [
                "C1",
                "C3",
                "C4"
              ],
              "loss": 8,
              "optional_cost": 3,
              "total_cost": 3,
              "w2": 2,
              "w3": 1
            },
            {
              "deleted_ids": [
                "C2",
                "C3",
                "C4"
              ],
              "loss": 9,
              "optional_cost": 3,
              "total_cost": 3,
              "w2": 1,
              "w3": 0
            }
          ],
          "status": "ok"
        },
        {
          "R": 8,
          "baseline": {
            "w2": 10,
            "w3": 4
          },
          "forced_cost": 0,
          "min_w2": 2,
          "profiles": [
            {
              "deleted_ids": [
                "A2",
                "A4"
              ],
              "loss": 0,
              "optional_cost": 2,
              "total_cost": 2,
              "w2": 10,
              "w3": 0
            },
            {
              "deleted_ids": [
                "A2"
              ],
              "loss": 0,
              "optional_cost": 1,
              "total_cost": 1,
              "w2": 10,
              "w3": 1
            },
            {
              "deleted_ids": [
                "A4"
              ],
              "loss": 0,
              "optional_cost": 1,
              "total_cost": 1,
              "w2": 10,
              "w3": 3
            },
            {
              "deleted_ids": [],
              "loss": 0,
              "optional_cost": 0,
              "total_cost": 0,
              "w2": 10,
              "w3": 4
            },
            {
              "deleted_ids": [
                "A2",
                "A4",
                "C1"
              ],
              "loss": 1,
              "optional_cost": 3,
              "total_cost": 3,
              "w2": 9,
              "w3": 0
            },
            {
              "deleted_ids": [
                "A2",
                "C1"
              ],
              "loss": 1,
              "optional_cost": 2,
              "total_cost": 2,
              "w2": 9,
              "w3": 1
            },
            {
              "deleted_ids": [
                "A4",
                "C1"
              ],
              "loss": 1,
              "optional_cost": 2,
              "total_cost": 2,
              "w2": 9,
              "w3": 3
            },
            {
              "deleted_ids": [
                "C1"
              ],
              "loss": 1,
              "optional_cost": 1,
              "total_cost": 1,
              "w2": 9,
              "w3": 4
            },
            {
              "deleted_ids": [
                "A2",
                "A4",
                "C2"
              ],
              "loss": 2,
              "optional_cost": 3,
              "total_cost": 3,
              "w2": 8,
              "w3": 0
            },
            {
              "deleted_ids": [
                "A2",
                "C2"
              ],
              "loss": 2,
              "optional_cost": 2,
              "total_cost": 2,
              "w2": 8,
              "w3": 1
            },
            {
              "deleted_ids": [
                "A4",
                "C2"
              ],
              "loss": 2,
              "optional_cost": 2,
              "total_cost": 2,
              "w2": 8,
              "w3": 2
            },
            {
              "deleted_ids": [
                "C2"
              ],
              "loss": 2,
              "optional_cost": 1,
              "total_cost": 1,
              "w2": 8,
              "w3": 3
            },
            {
              "deleted_ids": [
                "A2",
                "A4",
                "C3"
              ],
              "loss": 3,
              "optional_cost": 3,
              "total_cost": 3,
              "w2": 7,
              "w3": 0
            },
            {
              "deleted_ids": [
                "A2",
                "C3"
              ],
              "loss": 3,
              "optional_cost": 2,
              "total_cost": 2,
              "w2": 7,
              "w3": 1
            },
            {
              "deleted_ids": [
                "A4",
                "C3"
              ],
              "loss": 3,
              "optional_cost": 2,
              "total_cost": 2,
              "w2": 7,
              "w3": 2
            },
            {
              "deleted_ids": [
                "C3"
              ],
              "loss": 3,
              "optional_cost": 1,
              "total_cost": 1,
              "w2": 7,
              "w3": 3
            },
            {
              "deleted_ids": [
                "A2",
                "C4"
              ],
              "loss": 4,
              "optional_cost": 2,
              "total_cost": 2,
              "w2": 6,
              "w3": 0
            },
            {
              "deleted_ids": [
                "A2",
                "C1",
                "C3"
              ],
              "loss": 4,
              "optional_cost": 3,
              "total_cost": 3,
              "w2": 6,
              "w3": 1
            },
            {
              "deleted_ids": [
                "C4"
              ],
              "loss": 4,
              "optional_cost": 1,
              "total_cost": 1,
              "w2": 6,
              "w3": 2
            },
            {
              "deleted_ids": [
                "C1",
                "C3"
              ],
              "loss": 4,
              "optional_cost": 2,
              "total_cost": 2,
              "w2": 6,
              "w3": 3
            },
            {
              "deleted_ids": [
                "A2",
                "C1",
                "C4"
              ],
              "loss": 5,
              "optional_cost": 3,
              "total_cost": 3,
              "w2": 5,
              "w3": 0
            },
            {
              "deleted_ids": [
                "A4",
                "C2",
                "C3"
              ],
              "loss": 5,
              "optional_cost": 3,
              "total_cost": 3,
              "w2": 5,
              "w3": 1
            },
            {
              "deleted_ids": [
                "C2",
                "C3"
              ],
              "loss": 5,
              "optional_cost": 2,
              "total_cost": 2,
              "w2": 5,
              "w3": 2
            },
            {
              "deleted_ids": [
                "A2",
                "C2",
                "C4"
              ],
              "loss": 6,
              "optional_cost": 3,
              "total_cost": 3,
              "w2": 4,
              "w3": 0
            },
            {
              "deleted_ids": [
                "C2",
                "C4"
              ],
              "loss": 6,
              "optional_cost": 2,
              "total_cost": 2,
              "w2": 4,
              "w3": 1
            },
            {
              "deleted_ids": [
                "C1",
                "C2",
                "C3"
              ],
              "loss": 6,
              "optional_cost": 3,
              "total_cost": 3,
              "w2": 4,
              "w3": 2
            },
            {
              "deleted_ids": [
                "A2",
                "C3",
                "C4"
              ],
              "loss": 7,
              "optional_cost": 3,
              "total_cost": 3,
              "w2": 3,
              "w3": 0
            },
            {
              "deleted_ids": [
                "C3",
                "C4"
              ],
              "loss": 7,
              "optional_cost": 2,
              "total_cost": 2,
              "w2": 3,
              "w3": 1
            },
            {
              "deleted_ids": [
                "A2",
                "C1",
                "C3",
                "C4"
              ],
              "loss": 8,
              "optional_cost": 4,
              "total_cost": 4,
              "w2": 2,
              "w3": 0
            },
            {
              "deleted_ids": [
                "C1",
                "C3",
                "C4"
              ],
              "loss": 8,
              "optional_cost": 3,
              "total_cost": 3,
              "w2": 2,
              "w3": 1
            }
          ],
          "status": "ok"
        },
        {
          "R": 7,
          "baseline": {
            "w2": 10,
            "w3": 4
          },
          "forced_cost": 0,
          "min_w2": 3,
          "profiles": [
            {
              "deleted_ids": [
                "A2",
                "A4"
              ],
              "loss": 0,
              "optional_cost": 2,
              "total_cost": 2,
              "w2": 10,
              "w3": 0
            },
            {
              "deleted_ids": [
                "A2"
              ],
              "loss": 0,
              "optional_cost": 1,
              "total_cost": 1,
              "w2": 10,
              "w3": 1
            },
            {
              "deleted_ids": [
                "A4"
              ],
              "loss": 0,
              "optional_cost": 1,
              "total_cost": 1,
              "w2": 10,
              "w3": 3
            },
            {
              "deleted_ids": [],
              "loss": 0,
              "optional_cost": 0,
              "total_cost": 0,
              "w2": 10,
              "w3": 4
            },
            {
              "deleted_ids": [
                "A2",
                "A4",
                "C1"
              ],
              "loss": 1,
              "optional_cost": 3,
              "total_cost": 3,
              "w2": 9,
              "w3": 0
            },
            {
              "deleted_ids": [
                "A2",
                "C1"
              ],
              "loss": 1,
              "optional_cost": 2,
              "total_cost": 2,
              "w2": 9,
              "w3": 1
            },
            {
              "deleted_ids": [
                "A4",
                "C1"
              ],
              "loss": 1,
              "optional_cost": 2,
              "total_cost": 2,
              "w2": 9,
              "w3": 3
            },
            {
              "deleted_ids": [
                "C1"
              ],
              "loss": 1,
              "optional_cost": 1,
              "total_cost": 1,
              "w2": 9,
              "w3": 4
            },
            {
              "deleted_ids": [
                "A2",
                "A4",
                "C2"
              ],
              "loss": 2,
              "optional_cost": 3,
              "total_cost": 3,
              "w2": 8,
              "w3": 0
            },
            {
              "deleted_ids": [
                "A2",
                "C2"
              ],
              "loss": 2,
              "optional_cost": 2,
              "total_cost": 2,
              "w2": 8,
              "w3": 1
            },
            {
              "deleted_ids": [
                "A4",
                "C2"
              ],
              "loss": 2,
              "optional_cost": 2,
              "total_cost": 2,
              "w2": 8,
              "w3": 2
            },
            {
              "deleted_ids": [
                "C2"
              ],
              "loss": 2,
              "optional_cost": 1,
              "total_cost": 1,
              "w2": 8,
              "w3": 3
            },
            {
              "deleted_ids": [
                "A2",
                "A4",
                "C3"
              ],
              "loss": 3,
              "optional_cost": 3,
              "total_cost": 3,
              "w2": 7,
              "w3": 0
            },
            {
              "deleted_ids": [
                "A2",
                "C3"
              ],
              "loss": 3,
              "optional_cost": 2,
              "total_cost": 2,
              "w2": 7,
              "w3": 1
            },
            {
              "deleted_ids": [
                "A4",
                "C3"
              ],
              "loss": 3,
              "optional_cost": 2,
              "total_cost": 2,
              "w2": 7,
              "w3": 2
            },
            {
              "deleted_ids": [
                "C3"
              ],
              "loss": 3,
              "optional_cost": 1,
              "total_cost": 1,
              "w2": 7,
              "w3": 3
            },
            {
              "deleted_ids": [
                "A2",
                "C4"
              ],
              "loss": 4,
              "optional_cost": 2,
              "total_cost": 2,
              "w2": 6,
              "w3": 0
            },
            {
              "deleted_ids": [
                "A2",
                "C1",
                "C3"
              ],
              "loss": 4,
              "optional_cost": 3,
              "total_cost": 3,
              "w2": 6,
              "w3": 1
            },
            {
              "deleted_ids": [
                "C4"
              ],
              "loss": 4,
              "optional_cost": 1,
              "total_cost": 1,
              "w2": 6,
              "w3": 2
            },
            {
              "deleted_ids": [
                "C1",
                "C3"
              ],
              "loss": 4,
              "optional_cost": 2,
              "total_cost": 2,
              "w2": 6,
              "w3": 3
            },
            {
              "deleted_ids": [
                "A2",
                "C1",
                "C4"
              ],
              "loss": 5,
              "optional_cost": 3,
              "total_cost": 3,
              "w2": 5,
              "w3": 0
            },
            {
              "deleted_ids": [
                "A4",
                "C2",
                "C3"
              ],
              "loss": 5,
              "optional_cost": 3,
              "total_cost": 3,
              "w2": 5,
              "w3": 1
            },
            {
              "deleted_ids": [
                "C2",
                "C3"
              ],
              "loss": 5,
              "optional_cost": 2,
              "total_cost": 2,
              "w2": 5,
              "w3": 2
            },
            {
              "deleted_ids": [
                "A2",
                "C2",
                "C4"
              ],
              "loss": 6,
              "optional_cost": 3,
              "total_cost": 3,
              "w2": 4,
              "w3": 0
            },
            {
              "deleted_ids": [
                "C2",
                "C4"
              ],
              "loss": 6,
              "optional_cost": 2,
              "total_cost": 2,
              "w2": 4,
              "w3": 1
            },
            {
              "deleted_ids": [
                "C1",
                "C2",
                "C3"
              ],
              "loss": 6,
              "optional_cost": 3,
              "total_cost": 3,
              "w2": 4,
              "w3": 2
            },
            {
              "deleted_ids": [
                "A2",
                "C3",
                "C4"
              ],
              "loss": 7,
              "optional_cost": 3,
              "total_cost": 3,
              "w2": 3,
              "w3": 0
            },
            {
              "deleted_ids": [
                "C3",
                "C4"
              ],
              "loss": 7,
              "optional_cost": 2,
              "total_cost": 2,
              "w2": 3,
              "w3": 1
            }
          ],
          "status": "ok"
        },
        {
          "R": 6,
          "baseline": {
            "w2": 10,
            "w3": 4
          },
          "forced_cost": 0,
          "min_w2": 4,
          "profiles": [
            {
              "deleted_ids": [
                "A2",
                "A4"
              ],
              "loss": 0,
              "optional_cost": 2,
              "total_cost": 2,
              "w2": 10,
              "w3": 0
            },
            {
              "deleted_ids": [
                "A2"
              ],
              "loss": 0,
              "optional_cost": 1,
              "total_cost": 1,
              "w2": 10,
              "w3": 1
            },
            {
              "deleted_ids": [
                "A4"
              ],
              "loss": 0,
              "optional_cost": 1,
              "total_cost": 1,
              "w2": 10,
              "w3": 3
            },
            {
              "deleted_ids": [],
              "loss": 0,
              "optional_cost": 0,
              "total_cost": 0,
              "w2": 10,
              "w3": 4
            },
            {
              "deleted_ids": [
                "A2",
                "A4",
                "C1"
              ],
              "loss": 1,
              "optional_cost": 3,
              "total_cost": 3,
              "w2": 9,
              "w3": 0
            },
            {
              "deleted_ids": [
                "A2",
                "C1"
              ],
              "loss": 1,
              "optional_cost": 2,
              "total_cost": 2,
              "w2": 9,
              "w3": 1
            },
            {
              "deleted_ids": [
                "A4",
                "C1"
              ],
              "loss": 1,
              "optional_cost": 2,
              "total_cost": 2,
              "w2": 9,
              "w3": 3
            },
            {
              "deleted_ids": [
                "C1"
              ],
              "loss": 1,
              "optional_cost": 1,
              "total_cost": 1,
              "w2": 9,
              "w3": 4
            },
            {
              "deleted_ids": [
                "A2",
                "A4",
                "C2"
              ],
              "loss": 2,
              "optional_cost": 3,
              "total_cost": 3,
              "w2": 8,
              "w3": 0
            },
            {
              "deleted_ids": [
                "A2",
                "C2"
              ],
              "loss": 2,
              "optional_cost": 2,
              "total_cost": 2,
              "w2": 8,
              "w3": 1
            },
            {
              "deleted_ids": [
                "A4",
                "C2"
              ],
              "loss": 2,
              "optional_cost": 2,
              "total_cost": 2,
              "w2": 8,
              "w3": 2
            },
            {
              "deleted_ids": [
                "C2"
              ],
              "loss": 2,
              "optional_cost": 1,
              "total_cost": 1,
              "w2": 8,
              "w3": 3
            },
            {
              "deleted_ids": [
                "A2",
                "A4",
                "C3"
              ],
              "loss": 3,
              "optional_cost": 3,
              "total_cost": 3,
              "w2": 7,
              "w3": 0
            },
            {
              "deleted_ids": [
                "A2",
                "C3"
              ],
              "loss": 3,
              "optional_cost": 2,
              "total_cost": 2,
              "w2": 7,
              "w3": 1
            },
            {
              "deleted_ids": [
                "A4",
                "C3"
              ],
              "loss": 3,
              "optional_cost": 2,
              "total_cost": 2,
              "w2": 7,
              "w3": 2
            },
            {
              "deleted_ids": [
                "C3"
              ],
              "loss": 3,
              "optional_cost": 1,
              "total_cost": 1,
              "w2": 7,
              "w3": 3
            },
            {
              "deleted_ids": [
                "A2",
                "C4"
              ],
              "loss": 4,
              "optional_cost": 2,
              "total_cost": 2,
              "w2": 6,
              "w3": 0
            },
            {
              "deleted_ids": [
                "A2",
                "C1",
                "C3"
              ],
              "loss": 4,
              "optional_cost": 3,
              "total_cost": 3,
              "w2": 6,
              "w3": 1
            },
            {
              "deleted_ids": [
                "C4"
              ],
              "loss": 4,
              "optional_cost": 1,
              "total_cost": 1,
              "w2": 6,
              "w3": 2
            },
            {
              "deleted_ids": [
                "C1",
                "C3"
              ],
              "loss": 4,
              "optional_cost": 2,
              "total_cost": 2,
              "w2": 6,
              "w3": 3
            },
            {
              "deleted_ids": [
                "A2",
                "C1",
                "C4"
              ],
              "loss": 5,
              "optional_cost": 3,
              "total_cost": 3,
              "w2": 5,
              "w3": 0
            },
            {
              "deleted_ids": [
                "A4",
                "C2",
                "C3"
              ],
              "loss": 5,
              "optional_cost": 3,
              "total_cost": 3,
              "w2": 5,
              "w3": 1
            },
            {
              "deleted_ids": [
                "C2",
                "C3"
              ],
              "loss": 5,
              "optional_cost": 2,
              "total_cost": 2,
              "w2": 5,
              "w3": 2
            },
            {
              "deleted_ids": [
                "A2",
                "C2",
                "C4"
              ],
              "loss": 6,
              "optional_cost": 3,
              "total_cost": 3,
              "w2": 4,
              "w3": 0
            },
            {
              "deleted_ids": [
                "C2",
                "C4"
              ],
              "loss": 6,
              "optional_cost": 2,
              "total_cost": 2,
              "w2": 4,
              "w3": 1
            },
            {
              "deleted_ids": [
                "C1",
                "C2",
                "C3"
              ],
              "loss": 6,
              "optional_cost": 3,
              "total_cost": 3,
              "w2": 4,
              "w3": 2
            }
          ],
          "status": "ok"
        },
        {
          "R": 5,
          "baseline": {
            "w2": 10,
            "w3": 4
          },
          "forced_cost": 0,
          "min_w2": 5,
          "profiles": [
            {
              "deleted_ids": [
                "A2",
                "A4"
              ],
              "loss": 0,
              "optional_cost": 2,
              "total_cost": 2,
              "w2": 10,
              "w3": 0
            },
            {
              "deleted_ids": [
                "A2"
              ],
              "loss": 0,
              "optional_cost": 1,
              "total_cost": 1,
              "w2": 10,
              "w3": 1
            },
            {
              "deleted_ids": [
                "A4"
              ],
              "loss": 0,
              "optional_cost": 1,
              "total_cost": 1,
              "w2": 10,
              "w3": 3
            },
            {
              "deleted_ids": [],
              "loss": 0,
              "optional_cost": 0,
              "total_cost": 0,
              "w2": 10,
              "w3": 4
            },
            {
              "deleted_ids": [
                "A2",
                "A4",
                "C1"
              ],
              "loss": 1,
              "optional_cost": 3,
              "total_cost": 3,
              "w2": 9,
              "w3": 0
            },
            {
              "deleted_ids": [
                "A2",
                "C1"
              ],
              "loss": 1,
              "optional_cost": 2,
              "total_cost": 2,
              "w2": 9,
              "w3": 1
            },
            {
              "deleted_ids": [
                "A4",
                "C1"
              ],
              "loss": 1,
              "optional_cost": 2,
              "total_cost": 2,
              "w2": 9,
              "w3": 3
            },
            {
              "deleted_ids": [
                "C1"
              ],
              "loss": 1,
              "optional_cost": 1,
              "total_cost": 1,
              "w2": 9,
              "w3": 4
            },
            {
              "deleted_ids": [
                "A2",
                "A4",
                "C2"
              ],
              "loss": 2,
              "optional_cost": 3,
              "total_cost": 3,
              "w2": 8,
              "w3": 0
            },
            {
              "deleted_ids": [
                "A2",
                "C2"
              ],
              "loss": 2,
              "optional_cost": 2,
              "total_cost": 2,
              "w2": 8,
              "w3": 1
            },
            {
              "deleted_ids": [
                "A4",
                "C2"
              ],
              "loss": 2,
              "optional_cost": 2,
              "total_cost": 2,
              "w2": 8,
              "w3": 2
            },
            {
              "deleted_ids": [
                "C2"
              ],
              "loss": 2,
              "optional_cost": 1,
              "total_cost": 1,
              "w2": 8,
              "w3": 3
            },
            {
              "deleted_ids": [
                "A2",
                "A4",
                "C3"
              ],
              "loss": 3,
              "optional_cost": 3,
              "total_cost": 3,
              "w2": 7,
              "w3": 0
            },
            {
              "deleted_ids": [
                "A2",
                "C3"
              ],
              "loss": 3,
              "optional_cost": 2,
              "total_cost": 2,
              "w2": 7,
              "w3": 1
            },
            {
              "deleted_ids": [
                "A4",
                "C3"
              ],
              "loss": 3,
              "optional_cost": 2,
              "total_cost": 2,
              "w2": 7,
              "w3": 2
            },
            {
              "deleted_ids": [
                "C3"
              ],
              "loss": 3,
              "optional_cost": 1,
              "total_cost": 1,
              "w2": 7,
              "w3": 3
            },
            {
              "deleted_ids": [
                "A2",
                "C4"
              ],
              "loss": 4,
              "optional_cost": 2,
              "total_cost": 2,
              "w2": 6,
              "w3": 0
            },
            {
              "deleted_ids": [
                "A2",
                "C1",
                "C3"
              ],
              "loss": 4,
              "optional_cost": 3,
              "total_cost": 3,
              "w2": 6,
              "w3": 1
            },
            {
              "deleted_ids": [
                "C4"
              ],
              "loss": 4,
              "optional_cost": 1,
              "total_cost": 1,
              "w2": 6,
              "w3": 2
            },
            {
              "deleted_ids": [
                "C1",
                "C3"
              ],
              "loss": 4,
              "optional_cost": 2,
              "total_cost": 2,
              "w2": 6,
              "w3": 3
            },
            {
              "deleted_ids": [
                "A2",
                "C1",
                "C4"
              ],
              "loss": 5,
              "optional_cost": 3,
              "total_cost": 3,
              "w2": 5,
              "w3": 0
            },
            {
              "deleted_ids": [
                "A4",
                "C2",
                "C3"
              ],
              "loss": 5,
              "optional_cost": 3,
              "total_cost": 3,
              "w2": 5,
              "w3": 1
            },
            {
              "deleted_ids": [
                "C2",
                "C3"
              ],
              "loss": 5,
              "optional_cost": 2,
              "total_cost": 2,
              "w2": 5,
              "w3": 2
            }
          ],
          "status": "ok"
        },
        {
          "R": 4,
          "baseline": {
            "w2": 10,
            "w3": 4
          },
          "forced_cost": 0,
          "min_w2": 6,
          "profiles": [
            {
              "deleted_ids": [
                "A2",
                "A4"
              ],
              "loss": 0,
              "optional_cost": 2,
              "total_cost": 2,
              "w2": 10,
              "w3": 0
            },
            {
              "deleted_ids": [
                "A2"
              ],
              "loss": 0,
              "optional_cost": 1,
              "total_cost": 1,
              "w2": 10,
              "w3": 1
            },
            {
              "deleted_ids": [
                "A4"
              ],
              "loss": 0,
              "optional_cost": 1,
              "total_cost": 1,
              "w2": 10,
              "w3": 3
            },
            {
              "deleted_ids": [],
              "loss": 0,
              "optional_cost": 0,
              "total_cost": 0,
              "w2": 10,
              "w3": 4
            },
            {
              "deleted_ids": [
                "A2",
                "A4",
                "C1"
              ],
              "loss": 1,
              "optional_cost": 3,
              "total_cost": 3,
              "w2": 9,
              "w3": 0
            },
            {
              "deleted_ids": [
                "A2",
                "C1"
              ],
              "loss": 1,
              "optional_cost": 2,
              "total_cost": 2,
              "w2": 9,
              "w3": 1
            },
            {
              "deleted_ids": [
                "A4",
                "C1"
              ],
              "loss": 1,
              "optional_cost": 2,
              "total_cost": 2,
              "w2": 9,
              "w3": 3
            },
            {
              "deleted_ids": [
                "C1"
              ],
              "loss": 1,
              "optional_cost": 1,
              "total_cost": 1,
              "w2": 9,
              "w3": 4
            },
            {
              "deleted_ids": [
                "A2",
                "A4",
                "C2"
              ],
              "loss": 2,
              "optional_cost": 3,
              "total_cost": 3,
              "w2": 8,
              "w3": 0
            },
            {
              "deleted_ids": [
                "A2",
                "C2"
              ],
              "loss": 2,
              "optional_cost": 2,
              "total_cost": 2,
              "w2": 8,
              "w3": 1
            },
            {
              "deleted_ids": [
                "A4",
                "C2"
              ],
              "loss": 2,
              "optional_cost": 2,
              "total_cost": 2,
              "w2": 8,
              "w3": 2
            },
            {
              "deleted_ids": [
                "C2"
              ],
              "loss": 2,
              "optional_cost": 1,
              "total_cost": 1,
              "w2": 8,
              "w3": 3
            },
            {
              "deleted_ids": [
                "A2",
                "A4",
                "C3"
              ],
              "loss": 3,
              "optional_cost": 3,
              "total_cost": 3,
              "w2": 7,
              "w3": 0
            },
            {
              "deleted_ids": [
                "A2",
                "C3"
              ],
              "loss": 3,
              "optional_cost": 2,
              "total_cost": 2,
              "w2": 7,
              "w3": 1
            },
            {
              "deleted_ids": [
                "A4",
                "C3"
              ],
              "loss": 3,
              "optional_cost": 2,
              "total_cost": 2,
              "w2": 7,
              "w3": 2
            },
            {
              "deleted_ids": [
                "C3"
              ],
              "loss": 3,
              "optional_cost": 1,
              "total_cost": 1,
              "w2": 7,
              "w3": 3
            },
            {
              "deleted_ids": [
                "A2",
                "C4"
              ],
              "loss": 4,
              "optional_cost": 2,
              "total_cost": 2,
              "w2": 6,
              "w3": 0
            },
            {
              "deleted_ids": [
                "A2",
                "C1",
                "C3"
              ],
              "loss": 4,
              "optional_cost": 3,
              "total_cost": 3,
              "w2": 6,
              "w3": 1
            },
            {
              "deleted_ids": [
                "C4"
              ],
              "loss": 4,
              "optional_cost": 1,
              "total_cost": 1,
              "w2": 6,
              "w3": 2
            },
            {
              "deleted_ids": [
                "C1",
                "C3"
              ],
              "loss": 4,
              "optional_cost": 2,
              "total_cost": 2,
              "w2": 6,
              "w3": 3
            }
          ],
          "status": "ok"
        },
        {
          "R": 3,
          "baseline": {
            "w2": 10,
            "w3": 4
          },
          "forced_cost": 0,
          "min_w2": 7,
          "profiles": [
            {
              "deleted_ids": [
                "A2",
                "A4"
              ],
              "loss": 0,
              "optional_cost": 2,
              "total_cost": 2,
              "w2": 10,
              "w3": 0
            },
            {
              "deleted_ids": [
                "A2"
              ],
              "loss": 0,
              "optional_cost": 1,
              "total_cost": 1,
              "w2": 10,
              "w3": 1
            },
            {
              "deleted_ids": [
                "A4"
              ],
              "loss": 0,
              "optional_cost": 1,
              "total_cost": 1,
              "w2": 10,
              "w3": 3
            },
            {
              "deleted_ids": [],
              "loss": 0,
              "optional_cost": 0,
              "total_cost": 0,
              "w2": 10,
              "w3": 4
            },
            {
              "deleted_ids": [
                "A2",
                "A4",
                "C1"
              ],
              "loss": 1,
              "optional_cost": 3,
              "total_cost": 3,
              "w2": 9,
              "w3": 0
            },
            {
              "deleted_ids": [
                "A2",
                "C1"
              ],
              "loss": 1,
              "optional_cost": 2,
              "total_cost": 2,
              "w2": 9,
              "w3": 1
            },
            {
              "deleted_ids": [
                "A4",
                "C1"
              ],
              "loss": 1,
              "optional_cost": 2,
              "total_cost": 2,
              "w2": 9,
              "w3": 3
            },
            {
              "deleted_ids": [
                "C1"
              ],
              "loss": 1,
              "optional_cost": 1,
              "total_cost": 1,
              "w2": 9,
              "w3": 4
            },
            {
              "deleted_ids": [
                "A2",
                "A4",
                "C2"
              ],
              "loss": 2,
              "optional_cost": 3,
              "total_cost": 3,
              "w2": 8,
              "w3": 0
            },
            {
              "deleted_ids": [
                "A2",
                "C2"
              ],
              "loss": 2,
              "optional_cost": 2,
              "total_cost": 2,
              "w2": 8,
              "w3": 1
            },
            {
              "deleted_ids": [
                "A4",
                "C2"
              ],
              "loss": 2,
              "optional_cost": 2,
              "total_cost": 2,
              "w2": 8,
              "w3": 2
            },
            {
              "deleted_ids": [
                "C2"
              ],
              "loss": 2,
              "optional_cost": 1,
              "total_cost": 1,
              "w2": 8,
              "w3": 3
            },
            {
              "deleted_ids": [
                "A2",
                "A4",
                "C3"
              ],
              "loss": 3,
              "optional_cost": 3,
              "total_cost": 3,
              "w2": 7,
              "w3": 0
            },
            {
              "deleted_ids": [
                "A2",
                "C3"
              ],
              "loss": 3,
              "optional_cost": 2,
              "total_cost": 2,
              "w2": 7,
              "w3": 1
            },
            {
              "deleted_ids": [
                "A4",
                "C3"
              ],
              "loss": 3,
              "optional_cost": 2,
              "total_cost": 2,
              "w2": 7,
              "w3": 2
            },
            {
              "deleted_ids": [
                "C3"
              ],
              "loss": 3,
              "optional_cost": 1,
              "total_cost": 1,
              "w2": 7,
              "w3": 3
            }
          ],
          "status": "ok"
        },
        {
          "R": 2,
          "baseline": {
            "w2": 10,
            "w3": 4
          },
          "forced_cost": 0,
          "min_w2": 8,
          "profiles": [
            {
              "deleted_ids": [
                "A2",
                "A4"
              ],
              "loss": 0,
              "optional_cost": 2,
              "total_cost": 2,
              "w2": 10,
              "w3": 0
            },
            {
              "deleted_ids": [
                "A2"
              ],
              "loss": 0,
              "optional_cost": 1,
              "total_cost": 1,
              "w2": 10,
              "w3": 1
            },
            {
              "deleted_ids": [
                "A4"
              ],
              "loss": 0,
              "optional_cost": 1,
              "total_cost": 1,
              "w2": 10,
              "w3": 3
            },
            {
              "deleted_ids": [],
              "loss": 0,
              "optional_cost": 0,
              "total_cost": 0,
              "w2": 10,
              "w3": 4
            },
            {
              "deleted_ids": [
                "A2",
                "A4",
                "C1"
              ],
              "loss": 1,
              "optional_cost": 3,
              "total_cost": 3,
              "w2": 9,
              "w3": 0
            },
            {
              "deleted_ids": [
                "A2",
                "C1"
              ],
              "loss": 1,
              "optional_cost": 2,
              "total_cost": 2,
              "w2": 9,
              "w3": 1
            },
            {
              "deleted_ids": [
                "A4",
                "C1"
              ],
              "loss": 1,
              "optional_cost": 2,
              "total_cost": 2,
              "w2": 9,
              "w3": 3
            },
            {
              "deleted_ids": [
                "C1"
              ],
              "loss": 1,
              "optional_cost": 1,
              "total_cost": 1,
              "w2": 9,
              "w3": 4
            },
            {
              "deleted_ids": [
                "A2",
                "A4",
                "C2"
              ],
              "loss": 2,
              "optional_cost": 3,
              "total_cost": 3,
              "w2": 8,
              "w3": 0
            },
            {
              "deleted_ids": [
                "A2",
                "C2"
              ],
              "loss": 2,
              "optional_cost": 2,
              "total_cost": 2,
              "w2": 8,
              "w3": 1
            },
            {
              "deleted_ids": [
                "A4",
                "C2"
              ],
              "loss": 2,
              "optional_cost": 2,
              "total_cost": 2,
              "w2": 8,
              "w3": 2
            },
            {
              "deleted_ids": [
                "C2"
              ],
              "loss": 2,
              "optional_cost": 1,
              "total_cost": 1,
              "w2": 8,
              "w3": 3
            }
          ],
          "status": "ok"
        },
        {
          "R": 1,
          "baseline": {
            "w2": 10,
            "w3": 4
          },
          "forced_cost": 0,
          "min_w2": 9,
          "profiles": [
            {
              "deleted_ids": [
                "A2",
                "A4"
              ],
              "loss": 0,
              "optional_cost": 2,
              "total_cost": 2,
              "w2": 10,
              "w3": 0
            },
            {
              "deleted_ids": [
                "A2"
              ],
              "loss": 0,
              "optional_cost": 1,
              "total_cost": 1,
              "w2": 10,
              "w3": 1
            },
            {
              "deleted_ids": [
                "A4"
              ],
              "loss": 0,
              "optional_cost": 1,
              "total_cost": 1,
              "w2": 10,
              "w3": 3
            },
            {
              "deleted_ids": [],
              "loss": 0,
              "optional_cost": 0,
              "total_cost": 0,
              "w2": 10,
              "w3": 4
            },
            {
              "deleted_ids": [
                "A2",
                "A4",
                "C1"
              ],
              "loss": 1,
              "optional_cost": 3,
              "total_cost": 3,
              "w2": 9,
              "w3": 0
            },
            {
              "deleted_ids": [
                "A2",
                "C1"
              ],
              "loss": 1,
              "optional_cost": 2,
              "total_cost": 2,
              "w2": 9,
              "w3": 1
            },
            {
              "deleted_ids": [
                "A4",
                "C1"
              ],
              "loss": 1,
              "optional_cost": 2,
              "total_cost": 2,
              "w2": 9,
              "w3": 3
            },
            {
              "deleted_ids": [
                "C1"
              ],
              "loss": 1,
              "optional_cost": 1,
              "total_cost": 1,
              "w2": 9,
              "w3": 4
            }
          ],
          "status": "ok"
        },
        {
          "R": 0,
          "baseline": {
            "w2": 10,
            "w3": 4
          },
          "forced_cost": 0,
          "min_w2": 10,
          "profiles": [
            {
              "deleted_ids": [
                "A2",
                "A4"
              ],
              "loss": 0,
              "optional_cost": 2,
              "total_cost": 2,
              "w2": 10,
              "w3": 0
            },
            {
              "deleted_ids": [
                "A2"
              ],
              "loss": 0,
              "optional_cost": 1,
              "total_cost": 1,
              "w2": 10,
              "w3": 1
            },
            {
              "deleted_ids": [
                "A4"
              ],
              "loss": 0,
              "optional_cost": 1,
              "total_cost": 1,
              "w2": 10,
              "w3": 3
            },
            {
              "deleted_ids": [],
              "loss": 0,
              "optional_cost": 0,
              "total_cost": 0,
              "w2": 10,
              "w3": 4
            }
          ],
          "status": "ok"
        }
      ],
      "root": "z",
      "source_path": "illustration/instance.json",
      "title": "A larger worked example",
      "verification": {
        "legal_subsets": 64,
        "profile_witnesses": 230,
        "quota_tables": 11
      }
    }
  ],
  "schema_version": 1,
  "source": {
    "fixtures": [
      {
        "path": "implementation/examples/nonmonotone.json",
        "sha256": "0edf2604d82f4788759d13714bb593f7dbcb3b9fdae1ee5c0dac467109b6eb0d"
      },
      {
        "path": "implementation/examples/weighted_a.json",
        "sha256": "250f0d2e5dac5012a7681ad8efd9ff006789379606cfdeb97d35ae241d649ab1"
      },
      {
        "path": "implementation/examples/weighted_c.json",
        "sha256": "dbc8799dfe9bd9be454e61ac7c3cd094378e653397345735b7fe0d5184a2a3ff"
      },
      {
        "path": "implementation/examples/forced_baseline.json",
        "sha256": "2c9aa0fb6248be52538ae0ff98fc6d322e9c2c292e0cacc669b435a538a13921"
      },
      {
        "path": "illustration/instance.json",
        "sha256": "3f6c425b2c096c13349420cd6aa030c3added9c8bfd9a4f40e54661d37e45ec6"
      }
    ],
    "solver_path": "implementation/profile_solver.py",
    "solver_sha256": "a9f8f2c9f276055ab570940d784244192d177c16299f7a295ad75c481de7f4ba"
  },
  "verification": {
    "all_minimum_cost_tables_match": true,
    "all_witnesses_verified": true,
    "case_count": 5,
    "feasible_quota_tables": 22,
    "infeasible_quota_tables": 1,
    "legal_subsets": 78,
    "method": "Exhaustive legal original-ID deletion subsets and independent strict root-ending event-tuple counting",
    "profile_witnesses": 258,
    "quota_tables": 23,
    "scope": "Five bundled mathematical examples; not the IBM batch and not an independent human proof review."
  }
};
