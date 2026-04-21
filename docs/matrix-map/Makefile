# Matrix 地图维护
# 所有命令读 config.yaml + config.local.yaml，支持 ENV=test|prod|local

ENV ?= prod
PYTHON ?= python3
SCRIPT_DIR := scripts

# CLI override 透传（空就不加）
URL ?=
CALLER ?=
TOKEN_FILE ?=

EXTRA :=
ifneq ($(URL),)
  EXTRA += --url $(URL)
endif
ifneq ($(CALLER),)
  EXTRA += --caller $(CALLER)
endif
ifneq ($(TOKEN_FILE),)
  EXTRA += --token-file $(TOKEN_FILE)
endif

.PHONY: help sync validate build check all clean

help:
	@echo "Matrix 地图维护命令"
	@echo "  make sync                从 Matrix API 拉 live 数据（默认 env=prod）"
	@echo "  make sync ENV=test       切环境"
	@echo "  make sync URL=...        临时覆盖 URL"
	@echo "  make sync TOKEN_FILE=~/.tok  从文件读 token (推荐)"
	@echo "  make validate            校验全量 yaml 合规"
	@echo "  make validate-strict     warning 也按 error 处理"
	@echo "  make build               生成合并后的 MATRIX_OPS_MAP.yaml"
	@echo "  make check               sync + validate 一条龙"
	@echo "  make all                 sync + validate + build"
	@echo "  make clean               清 live/ 与生成物"
	@echo ""
	@echo "环境变量:"
	@echo "  MATRIX_PROD_TOKEN        prod token（推荐放 ~/.bashrc 等）"
	@echo "  MATRIX_TEST_TOKEN        test token"
	@echo "  MATRIX_LOCAL_TOKEN       local token"
	@echo "  MATRIX_ENV               等价 ENV="
	@echo "  MATRIX_URL               URL override"

sync:
	@$(PYTHON) $(SCRIPT_DIR)/sync.py --env $(ENV) $(EXTRA)

validate:
	@$(PYTHON) $(SCRIPT_DIR)/validate.py --env $(ENV)

validate-strict:
	@$(PYTHON) $(SCRIPT_DIR)/validate.py --env $(ENV) --strict

build:
	@$(PYTHON) $(SCRIPT_DIR)/build.py --env $(ENV)

check: sync validate

all: sync validate build

clean:
	@rm -f live/rooms.json live/last_sync.json MATRIX_OPS_MAP.yaml MATRIX_OPS_MAP.yaml.sha256
	@echo "已清理 live/ 和生成物"
