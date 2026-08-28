# Para ler/escrever arquivos no formato do excel
library(readxl)
# Para fazer o cálculo do QL
library(EconGeo)
# Para baixar shapefiles dos municípios
library(geobr)
library(REAT)
library(dplyr)
library(ggplot2)
library(sf)
library(ggspatial)

# Dados extraidos de https://bi.mte.gov.br/bgcaged/

# O arquivo csv importado deve conter nas linhas TODAS as subclasses CNAE.20
# e nas colunas os municipios.

# Para importar todas as subclases CNAE 2.0, basta marcar a opção de
# importar linhas zeradas na hora de realizar a consulta

formatar_dados_sidra <- function(caminho_dados_sidra)  {
  
  dados_tratados = read.csv(caminho_dados_sidra, 
                        sep= ';')
  
  dados_tratados = dados_tratados |>
    mutate(across(where(is.character), ~ case_when(
      . == "-" ~ "0",
      . == "..." ~ "0",
      TRUE ~ . 
    ))) |>
    mutate(across(-Município, as.integer))
  
  return(dados_tratados) 
}

tipo_regiao <- function(ce, rie, rse) {
  
  if ((is.na(ce)) || is.na(rie) || (is.na(rse))) {
    return('T-1')
  } else {
    sinais = c(sign(ce), sign(rie), sign(rse))
    if (all(sinais == c(1, 1, 1))) {
      return('T1')
    } else if (all(sinais == c(1, 1, -1))) {
      return('T2')
    } else if (all(sinais == c(1, -1, 1))) {
      return('T3')
    } else if (all(sinais == c(1, -1, -1))) {
      return('T4')
    } else if (all(sinais == c(-1, 1, 1))) {
      return('T5')
    } else if (all(sinais == c(-1, 1, -1))) {
      return('T6')
    } else if (all(sinais == c(-1, -1, 1))) {
      return('T7')
    } else if (all(sinais == c(-1, -1, -1))) {
      return('T8') 
    } else {
      return('T-1')
    }
    
  }
  
  
}

shift.montania.marquez <- function(region_t, region_t1, nation_t, nation_t1) {
  
  industries <- length(region_t)
  
  sum_region_t <- sum(region_t)
  sum_region_t1 <- sum(region_t1)
  sum_nation_t <- sum(nation_t)
  sum_nation_t1 <- sum(nation_t1)
  
  # novos componentes de taxas de crescimento e homotetico
  G <- vector()
  g <- vector()
  gi <- vector()
  Gi <- vector()
  
  # NS_tir <- vector()
  NE <- vector()
  
  # IM_tir <- vector()
  IM <- vector()
  
  # RS_tir <- vector()
  CE <- vector()
  RIE <- vector()
  RSE <- vector()
  RCCE <- vector()
  
  Estoque_mun_t0  <- vector()
  Estoque_mun_t1 <- vector()
  Estoque_nac_t0  <- vector()
  Estoque_nac_t1 <- vector()
  VarTot <- vector()
  conferencia <- vector()
  status <- vector()
  classificacao_regiao <- vector()
  
  
  
  for (i in 1:industries) {
    # Se o estoque da subalsse foi zero em ambos os anos retorna status 2
    if ((region_t[i] == 0) & (region_t1[i] == 0)) {
      
      status[i] <- 2
      
      # Se o estoque em t0 era de 0 e em t1 foi positivo, retorna status 1
    } else if ((region_t[i] == 0) & (region_t1[i] > 0)) {
      
      status[i] <- 1
      
      # Tudo ok em outras situações
    } else {
      status[i] <- 0
    }
    
    G[i] <- (sum_nation_t1 - sum_nation_t)/sum_nation_t
    
    g[i] <- (sum_region_t1 - sum_region_t)/sum_region_t
    
    gi[i] <- (region_t1[i] - region_t[i])/region_t[i]
    
    Gi[i] <- (nation_t1[i] - nation_t[i])/nation_t[i]
    
    # componentes
    
    NE[i] <- G[i]*region_t[i]
    
    IM[i] <- (Gi[i] - G[i])*region_t[i]
    
    CE[i] <- (gi[i] - Gi[i])*region_t[i]
    
    RIE[i] <- (gi[i] - g[i])*region_t[i]
    
    RSE[i] <- (g[i] - G[i])*region_t[i]
    
    RCCE[i] <- (G[i] - gi[i])*region_t[i]
    
    Estoque_mun_t0[i] <- region_t[i]
    
    Estoque_mun_t1[i] <- region_t1[i]
    
    Estoque_nac_t0[i]  <- nation_t[i]
    
    Estoque_nac_t1[i] <- nation_t1[i]
    
    VarTot[i] <- NE[i] + IM[i] + CE[i] + RIE[i] + RSE[i] + RCCE[i]
    
    conferencia[i] <- region_t1[i] - region_t[i]
    
    classificacao_regiao[i]  <- tipo_regiao(CE[i], RIE[i], RSE[i])
    
  }
  shifts <- list(NE = NE, IM = IM, CE = CE, RIE = RIE, RSE = RSE, RCCE = RCCE, 
                 Estoque_mun_t0 = Estoque_mun_t0, Estoque_mun_t1 = Estoque_mun_t1,
                 Estoque_nac_t0 = Estoque_nac_t0, Estoque_nac_t1 = Estoque_nac_t1,
                 VarTot = VarTot, conferencia = conferencia, status = status,
                 classificacao_regiao = classificacao_regiao)
  return(shifts)
  
}

ANO_T1 = 2024

# Faço o Shift-shaqre pra 10 anos atras, 5 anos, e 1 ano
ANOS = c(ANO_T1- 11, ANO_T1 - 6, ANO_T1 - 2)

REGIOES = c('Piauí', 'Nordeste', 'Brasil')

consolidado = data.frame()


for (ANO_T0 in ANOS) {
  # Le os dados de emprego para os municipios do Piaui no ano T0 e T1
  
  # Dados de emprego municipio Piaui ano T0
  emprego_t0 <- formatar_dados_sidra (paste0('../Dados/PPM_Efetivo_rebanhos_',ANO_T0,'_municipiosPI.csv'))

  emprego_t1 <- formatar_dados_sidra (paste0('../Dados/PPM_Efetivo_rebanhos_',ANO_T1,'_municipiosPI.csv')) 
  
  for (regiao in REGIOES) {
      
      for (mun in emprego_t1$Município) {
        
        print(paste0("Shift share ", ANO_T0, " Nível nacional: ", regiao, " de: ", mun))
        
        # Criar os dados para passar para a função
        mun_t0 = emprego_t0 |>
          filter(Município == mun)
        
        mun_t1 = emprego_t1 |>
          filter(Município == mun)
        
        mun_t0 = as.matrix(mun_t0[1,2:ncol(mun_t0)])
        mun_t1 = as.matrix(mun_t1[1,2:ncol(mun_t1)])
        
        regiao_t0 = emprego_t0 |> filter(Município == regiao)
        regiao_t0 = as.matrix(regiao_t0[1,2:ncol(emprego_t0)])
        
        regiao_t1 = emprego_t1 |> filter(Município == regiao)
        regiao_t1 = as.matrix(regiao_t1[1,2:ncol(emprego_t0)])
        
        
        results <- shift.montania.marquez(mun_t0, mun_t1,
                                          regiao_t0, regiao_t1)
        
        industrias = colnames(emprego_t0[,2:ncol(emprego_t0)])
        
        tabela = as.data.frame(results)
        tabela$subclasse <- industrias 
        tabela$NM_MUN_RAIS = mun
        tabela$ANO_T0 <- ANO_T0
        tabela$ANO_T1 <- ANO_T1
        tabela$REFERENCIA_GEOGRAFICA <- regiao
        
        consolidado = rbind(consolidado, tabela)
        
      }
  } 
}


consolidado |>
  write.table(file = 'shift-share-consolidado_ppm_efetivo_rebanhos.csv', 
              dec = ',', 
              sep = ';', 
              fileEncoding = 'latin1',
              na = "",
              row.names = FALSE)
