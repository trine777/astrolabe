# Matrix 地图维护
# 所有命令读 config.yaml + config.local.yaml，支持 ENV=test|prod|local

ENV ?= test
PYTHON ?= python3
SCRIPT_DIR := scripts

.PHONY: help sync validate build check all clean

help:
	@echo "Matrix 地图维护命令"
	@echo "  make sync                从 Matrix API 拉 live 数据（默认 env=test）"
	@echo "  make sync ENV=prod       切环境"
	@echo "  make validate            校验全量 yaml 合规"
	@echo "  make validate-strict     warning 也按 error 处理"
	@echo "  make build               生成合并后的 MATRIX_OPS_MAP.yaml"
	@echo "  make check               sync + validate + build 一条龙"
	@echo "  make clean               清 live/ 与生成物"
	@echo ""
	@echo "环境变量:"
	@echo "  MATRIX_TEST_TOKEN / MATRIX_PROD_TOKEN   分环境 token（推荐）"
	@echo "  MATRIX_TOKEN                            通用 token override"
	@echo "  MATRIX_URL                              URL override"

sync:
	@$(PYTHON) $(SCRIPT_DIR)/sync.py --env $(ENV)

validate:
	@$(PYTHON) $(SCRIPT_DIR)/validate.py --env $(ENV)

validate-strict:
	@$(PYTHON) $(SCRIPT_DIR)/validate.py --env $(ENV) --strict

build:
	@$(PYTHON) $(SCRIPT_DIR)/build.py --env $(ENV)

check: sync validate

all: sync validate build

clean:
	@rm -f live/rooms.json live/last_sync.json MATRIX_OPS_MAP.yaml
	@echo "已清理 live/ 和生成物"
