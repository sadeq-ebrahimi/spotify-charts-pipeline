resource "azurerm_resource_group" "main" {
  name     = "rg-${var.project_name}"
  location = var.location
}

resource "azurerm_storage_account" "datalake" {
  name                     = "st${var.project_name}dl"
  resource_group_name      = azurerm_resource_group.main.name
  location                 = azurerm_resource_group.main.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
}

resource "azurerm_storage_container" "raw" {
  name                  = "spotify-raw"
  storage_account_name  = azurerm_storage_account.datalake.name
  container_access_type = "private"
}

resource "azurerm_mssql_server" "main" {
  name                         = "sql-${var.project_name}"
  resource_group_name          = azurerm_resource_group.main.name
  location                     = azurerm_resource_group.main.location
  version                      = "12.0"
  administrator_login          = var.sql_admin_username
  administrator_login_password = var.sql_admin_password
}

resource "azurerm_mssql_database" "warehouse" {
  name                 = "spotify_warehouse"
  server_id            = azurerm_mssql_server.main.id
  sku_name             = "Basic" # cheapest tier, fine for this project
  max_size_gb          = 2
  storage_account_type = "Local"
}

# Allow Azure services (like your ingestion script) to reach the SQL server
resource "azurerm_mssql_firewall_rule" "allow_azure_services" {
  name             = "AllowAzureServices"
  server_id        = azurerm_mssql_server.main.id
  start_ip_address = "0.0.0.0"
  end_ip_address   = "0.0.0.0"
}

# Allow your Codespace's IP to connect too (see step 5 below)
resource "azurerm_mssql_firewall_rule" "allow_dev" {
  name             = "AllowDevMachine"
  server_id        = azurerm_mssql_server.main.id
  start_ip_address = var.dev_ip_address
  end_ip_address   = var.dev_ip_address
}